import sys
import random
from collections import defaultdict
from itertools import product

def getchar(file):
	for line in file:
		for c in line: yield c

class IStream():
	def __init__(self, input):
		self.cstream = getchar(input)
		try:
			self.c = self.cstream.next()
		except StopIteration:
			self.c = ""

	def peek(self):
		return self.c
	
	def next(self):
		last = self.c
		try:
			self.c = self.cstream.next()
		except StopIteration:
			self.c = ""
		return last

class SynModel():
	def __init__(self, syntax, vars, start):
		self.grammar = {
			v: (sum(map(lambda t: t[1], rules)), rules)
			for v, rules in syntax.iteritems() 
		}
		self.vars = vars
		self.start = start

	def select(self, v):
		total, rules = self.grammar[v]
		r = random.uniform(0, total)
		for c, w in rules:
			r -= w
			if r <= 0:
				return c

	def generate(self):
		index = 0
		syms = self.select(self.start)
		slots = []
		while index < len(syms):
			type, sym = syms[index]
			if type == '$':
				syms[index:index+1] = self.select(sym)
			else:
				slots.append(self.vars[sym])
				index += 1
		return slots

def charModel(conds, vars):
	model = dict()
	for (v1, v2, v3) in conds:
		fchars = ['_'] if v1 == '_' else vars[v1].keys()
		schars = ['_'] if v2 == '_' else vars[v2].keys()
		dist = vars[v3]
		for pair in product(fchars, schars):
			if pair in model:
				ndist = model[pair].copy()
				for c, freq in dist.iteritems():
					ndist[c] += freq
				model[pair] = ndist
			else:
				model[pair] = dist
	return model

class WordModel():
	def __init__(self, syntax, conds, vars, start):
		self.synmodel = SynModel(syntax, vars, start)
		self.charmodel = charModel(conds, vars)
	
	def generate(self):
		slots = self.synmodel.generate()
		clist = ['_', '_']

		#iterate over distributions for each slot
		for sdist in slots:
			#get conditional trigram distribution, if it exists
			pair = tuple(clist[-2:])
			if pair in self.charmodel:
				cdist = self.charmodel[tuple(clist[-2:])]
				#intersect the two distributions
				ndist = {
					char: weight*cdist[char]
					for char, weight in sdist.iteritems()
					if char in cdist
				}
			else:
				ndist = sdist

			#select a character for this slot in the word
			total = sum(ndist.values())
			r = random.uniform(0, total)
			for c, w in ndist.iteritems():
				r -= w
				if r <= 0:
					clist.append(c)
					break
		return ''.join(clist[2:])

def skipWhite(input):
	while input.peek() == ' ':
		input.next()

def getN(input, n):
	s = ""
	while n > 0:
		s += input.next()
		n -= 1
	return s

def getToken(input, terminals = []):
	s = ""
	exclude = terminals + [' ', '\n']
	while input.peek() not in exclude:
		s += input.next()
	return s

def parseChar(input):
	freq = 1
	skipWhite(input)
	char = getToken(input, terminals = ['>', '*'])
	skipWhite(input)
	if input.peek() == '*':
		input.next()
		freq = float(getToken(input, terminals = ['>']))
	return (char, freq)

nextvar = 0
def genvar():
	global nextvar
	nextvar += 1
	return str(nextvar)

def parseClass(input, vars):
	chars = defaultdict(float)
	input.next() #skip <
	while input.peek() != '>':
		char, freq = parseChar(input)
		chars[char] += freq
		skipWhite(input)
	input.next() #skip >
	varname = genvar()
	vars[varname] = chars
	return varname

def getClassVar(input, vars):
	skipWhite(input)
	c = input.peek()
	if c == '_':
		return input.next()
	elif c == '#':
		return getToken(input)
	elif c == '<':
		return parseClass(input, vars)
	else:
		raise Exception("Expected character class; saw: " + c)

def parseSyntax(input, syntax, vars):
	sym = getToken(input)
	freq = 1
	vlist = []

	skipWhite(input)
	if getN(input, 2) != '->':
		raise Exception("Expected -> in syntax definition")
	skipWhite(input)

	c = input.peek()
	while c != '\n':
		if c == '#' or c == '<':
			vlist.append(('#', getClassVar(input, vars)))
		elif c == '$':
			vlist.append(('$', getToken(input)))
		elif c == '*':
			input.next()
			freq = float(getToken(input))
		else:
			raise Exception("Expected Syntax Variable, Character Class, or Frequency; saw: " + c)

		skipWhite(input)
		c = input.peek()

	if sym in syntax:
		syntax[sym].append((vlist, freq))
	else:
		syntax[sym] = [(vlist, freq)]

	return sym

def parseCondition(input, v1, v2, conds, vars):
	skipWhite(input)
	if getN(input, 2) != '->':
		raise Exception("Expected -> in Conditional Probability statement")
	conds.append((v1, v2, getClassVar(input, vars)))

def parseDefinition(input, v, vars):
	input.next() #skip '='
	vars[v] = vars[getClassVar(input, vars)]

def parseCondOrDef(input, conds, vars):
	var1 = getClassVar(input, vars)
	
	skipWhite(input)

	c = input.peek()
	if c == "=":
		if var1 == '_':
			raise Exception("_ cannot occur in Definitions")
		parseDefinition(input, var1, vars)
		return

	var2 = getClassVar(input, vars)
	if var2 == "_" and var1 != "_":
		raise Exception("_ cannot occur after a Character Class")

	parseCondition(input, var1, var2, conds, vars)

def parse(input):
	syntax = dict()
	vars = dict()
	conds = []
	start = None
	while input.peek() != "":
		skipWhite(input)
		c = input.peek()
		if c == "$":
			sym = parseSyntax(input, syntax, vars)
			if start is None:
				start = sym
		elif c in ["#", "_", "<"]:
			parseCondOrDef(input, conds, vars)
		else:
			while input.peek() != '\n':
				input.next()
			input.next()
	return WordModel(syntax, conds, vars, start)

model = parse(IStream(sys.stdin))
words = set()
target = int(sys.argv[1]) if len(sys.argv) > 1 else 10
while len(words) < target:
	words.add(model.generate())
for w in sorted(words):
	print w
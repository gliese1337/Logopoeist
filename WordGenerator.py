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
	for (prevars, postvar) in conds:
		pres = map(lambda v: ['_'] if v == '_' else vars[v].keys(), prevars)
		dist = vars[postvar]
		for ngram in product(*pres):
			if ngram in model:
				ndist = model[ngram].copy()
				for c, freq in dist.iteritems():
					ndist[c] += freq
				model[ngram] = ndist
			else:
				model[ngram] = dist
	return model

def exclusionModel(excls, vars):
	model = dict()
	for (prevars, postvar) in excls:
		pres = map(lambda v: ['_'] if v == '_' else vars[v].keys(), prevars)
		dist = set(vars[postvar].keys())
		for ngram in product(*pres):
			if ngram not in model:
				model[ngram] = dist.copy()
			else:
				model[ngram].update(dist)
	return model


class WordModel():
	def __init__(self, syntax, conds, excls, vars, start):
		self.synmodel = SynModel(syntax, vars, start)
		self.conditions = charModel(conds, vars)
		self.exclusions = exclusionModel(excls, vars)
	
	def generate(self):
		slots = self.synmodel.generate()
		clist = ['_']

		#iterate over distributions for each slot
		for i, sdist in enumerate(slots):
			ndist = sdist
			#iterate over conditioning ngrams
			for j in xrange(1,i+2):
				ngram = tuple(clist[-j:])
				
				#remove any exclusions
				if ngram in self.exclusions:
					for char in self.exclusions[ngram]:
						if char in ndist: del ndist[char]

				#intersect conditioning distributions
				if ngram in self.conditions:
					cdist = self.conditions[ngram]
					ndist = {
						char: weight*cdist[char]
						for char, weight in ndist.iteritems()
						if char in cdist
					}

			#select a character for this slot in the word
			total = sum(ndist.values())
			r = random.uniform(0, total)
			for c, w in ndist.iteritems():
				r -= w
				if r <= 0:
					clist.append(c)
					break

		return ''.join(clist[1:])

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
	if c == '#':
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
	while c not in ['\n', ';']:
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

def parseCondition(input, cond_vars, conds, excls, vars):
	skipWhite(input)
	arrow = getN(input, 2)
	if arrow == '->':
		conds.append((cond_vars, getClassVar(input, vars)))
	elif arrow == '!>':
		excls.append((cond_vars, getClassVar(input, vars)))
	else:
		raise Exception("Expected -> or !> in Conditional Probability statement")

def parseDefinition(input, v, vars):
	input.next() #skip '='
	vars[v] = vars[getClassVar(input, vars)]

def parseCondOrDef(input, conds, excls, vars):
	skipWhite(input)
	var1 = input.next() if input.peek() == '_'\
						else getClassVar(input, vars)
	
	skipWhite(input)
	c = input.peek()
	if c == "=":
		if var1 == '_':
			raise Exception("_ cannot occur in Definitions")
		parseDefinition(input, var1, vars)
		return

	cond_vars = [var1]
	while True:
		try:
			cond_vars.append(getClassVar(input, vars))
		except: break

	parseCondition(input, tuple(cond_vars), conds, excls, vars)

def parse(input):
	syntax = dict()
	vars = dict()
	conds, excls = [], []
	start = None
	while input.peek() != "":
		skipWhite(input)
		c = input.peek()
		if c == "$":
			sym = parseSyntax(input, syntax, vars)
			if start is None:
				start = sym
		elif c in ["#", "_", "<"]:
			parseCondOrDef(input, conds, excls, vars)
		elif c in [';', '\r', '\n']:
			while input.peek() not in ['\n','']:
				input.next()
			input.next()
		else:
			raise Exception("Syntax Error; Unexpected "+repr(c))
	return WordModel(syntax, conds, excls, vars, start)

model = parse(IStream(sys.stdin))
words = set()
target = int(sys.argv[1]) if len(sys.argv) > 1 else 10
while len(words) < target:
	word = model.generate()
	if word not in words:
		words.add(word)
		print word
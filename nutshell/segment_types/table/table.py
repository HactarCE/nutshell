"""Facilitates parsing of a nutshell rule into an abstract, compiler.py-readable format."""
import re
from collections import Iterable
from functools import partial
from itertools import chain, cycle, islice, zip_longest

import bidict

from nutshell.common.classes import TableRange
from nutshell.common.utils import printv, printq
from nutshell.common.errors import *
from .lark_assets import parser as lark_standalone
from ._transformer import Preprocess, NUTSHELL_GRAMMAR
from ._classes import VarName, StateList
from . import _symutils as symutils


def generate_cardinals(d):
    """{'name': ('N', 'E', ...)} >>> {'name': {'N' :: 1, 'E' :: 2, ...}}"""
    return {k: bidict.bidict(map(reversed, enumerate(v, 1))) for k, v in d.items()}


class Bidict(bidict.bidict):
    on_dup_kv = bidict.OVERWRITE


class Table:
    CARDINALS = generate_cardinals({
      'oneDimensional': ('W', 'E'),
      'vonNeumann': ('N', 'E', 'S', 'W'),
      'hexagonal': ('N', 'E', 'SE', 'S', 'W', 'NW'),
      'Moore': ('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'),
      })
    TRLENS = {k: len(v) for k, v in CARDINALS.items()}
    hush = True

    def __init__(self, tbl, start=0, *, dep: ['@NUTSHELL'] = None):
        # parser or lexer dies if there are blank lines right at the start
        # so idk
        while not tbl[0].split('#', 1)[0].strip():
            del tbl[0]
            start += 1
        self._src = tbl
        self.start = start
        self._n_states = 0
        self.comments = {}
        self._nbhd = self._trlen = None
        dep, = dep
        
        if self.hush:
            global printv, printq
            printv = printq = lambda *_, **__: None
        
        if dep is not None:
            dep.replace(self._src)
            self._constants = dep.constants
            if self._constants:
                self._n_states = max(self._constants.values())
        
        self.directives = {'neighborhood': 'Moore', 'symmetries': 'none', 'states': self._n_states}
        self.vars = Bidict()  # {VarName(name) | str(name) :: Variable(value)}
        self.sym_types = set()
        self.transitions = []
        self._constants = {}

        self.specials = {'any': VarName('any'), 'live': VarName('live')}
        self.new_varname = VarName.new_generator()
        
        trans = Preprocess(tbl=self)
        parser = lark_standalone.Lark_StandAlone(tbl=self)
        try:
            _parsed = parser.parse('\n'.join(self._src))
        except lark_standalone.UnexpectedCharacters as e:
            raise SyntaxErr(
              (e.line, e.column, 1+e.column),
              f"Unexpected character {{span!r}}{f' (expected {e.allowed})' if e.allowed else ''}",
              shift=self.start
              )
        except lark_standalone.UnexpectedToken as e:
            raise SyntaxErr(
              (e.line, e.column, 1+e.column),
              f"Unexpected token {{span!r}} (expected {'/'.join(e.expected)})",
              shift=self.start
              )
        else:
            self.update_special_vars()
        self._data = trans.transform(_parsed)
        
        if len(self.sym_types) <= 1 and not hasattr(next(iter(self.sym_types), None), 'fallback'):
            self.final = [t.fix_vars() for t in self._data]
        else:
            min_sym = symutils.find_min_sym_type(self.sym_types, self.trlen)
            self.directives['symmetries'] = min_sym.name[0] if hasattr(min_sym, 'name') else min_sym.__name__.lower()
            self.final = [new_tr for tr in self._data for new_tr in tr.in_symmetry(min_sym)]
        self.directives['n_states'] = self.directives.pop('states')
    
    def __getitem__(self, item):
        return self._src[item]
    
    def __iter__(self):
        yield from self.final
    
    @property
    def neighborhood(self):
        if self._nbhd is None:
            self._nbhd = self.CARDINALS[self.directives['neighborhood']]
        return self._nbhd

    @property
    def trlen(self):
        if self._trlen is None:
            self._trlen = len(self.neighborhood)
        return self._trlen
    
    @property
    def symmetries(self):
        return symutils.get_sym_type(self.directives['symmetries'])
    
    @property
    def n_states(self):
        return self._n_states
    
    @n_states.setter
    def n_states(self, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            if value == '?':
                self.directives['states'] = self._n_states
        else:
            self._n_states = self.directives['states'] = value
    
    def update_special_vars(self, value=None):
        if value is not None:
            self.n_states = value
        self.vars[self.specials['any']] = StateList(range(self.n_states), context=None)
        self.vars[self.specials['live']] = StateList(range(1, self.n_states), context=None)
    
    def add_sym_type(self, name):
        self.sym_types.add(symutils.get_sym_type(name))
    
    def check_cdir(self, cdir, meta, *, return_int=True, enforce_int=False):
        if enforce_int and hasattr(self.symmetries, 'special') and not cdir.isdigit():
            raise SyntaxErr(
              meta,
              f"Compass directions have no meaning under {self.directives['symmetries']} symmetry. "
              f'Instead, refer to previous states using numbers 0..8: here, {cdir} would be {self.neighborhood[cdir]}'
              )
        try:
            if return_int:
                return int(cdir) if cdir.isdigit() else self.neighborhood[str(cdir)]
            return int(cdir != '0') and self.neighborhood.inv[int(cdir)] if cdir.isdigit() else str(cdir)
        except KeyError:
            pre = 'Transition index' if cdir.isdigit() else 'Compass direction'
            raise ReferenceErr(
              meta,
              f"{pre} {cdir} does not exist in {self.directives['neighborhood']} neighborhood"
              )
    
    def match(self, tr):
        printq('Complete!\n\nSearching for match...')
        start, *in_napkin, end = tr
        if len(in_napkin) != self.trlen:
            raise ValueErr(None, f'Bad length for match (expected {2+self.trlen} states, got {2+len(in_napkin)})')
        in_trs = [(start, *napkin, end) for napkin in self.symmetries(in_napkin).expand()]
        for tr in self._data:
            for in_tr in in_trs:
                for cur_len, (in_state, tr_state) in enumerate(zip(in_tr, tr), -1):
                    if in_state != '*' and not (in_state in tr_state if isinstance(tr_state, Iterable) else in_state == getattr(tr_state, 'value', tr_state)):
                        if cur_len == self.trlen:
                            lno, start, end = tr.ctx
                            return (
                              'No match\n\n'
                              f'Impossible match!\nOverridden on line {self.start+lno} by:\n  {self[lno-1]}\n'
                              f"""{"" if start == 1 else f"  {' '*(start-1)}{'^'*(end-start)}"}\n"""  # TODO FIXME: deuglify
                              f"Specifically (compiled line):\n  {', '.join(map(str, tr.fix_vars()))}"
                              )
                        break
                else:
                    lno, start, end = tr.ctx
                    return (
                      'Found!\n\n'
                      f'Line {self.start+lno}:\n  {self[lno-1]}\n'
                      f"""{"" if start == 1 else f"  {' '*(start-1)}{'^'*(end-start)}"}\n"""  # TODO FIXME: deuglify
                      f"Compiled line:\n  {', '.join(map(str, tr.fix_vars()))}"
                      )
        if start == end:
            return 'No match\n\nThis transition is the result of unspecified default behavior'
        return 'No match'

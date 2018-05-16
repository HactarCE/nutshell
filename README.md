# rueltabel
A transpiler from a reimagined Golly ruletable language to the traditional format. See [`examples/`](/examples) for examples.

## Setup

1. [Download & install Python 3.6](https://www.python.org/downloads/release/python-365/) or higher (support for < 3.6 hopefully coming soon)
2. `git clone` this project, then `cd` to its directory
3. Using Python's bundled *pip* package manager, execute the terminal command `pip install -r requirements.txt` (or
   any of its variations -- you may need to try `python -m pip install`, `python3 -m pip install`, `py -m pip install`
   on Windows, ...)
4. Write your own rueltabel, then continue with the **Usage** section below.

## Usage
```bash
$ python to_ruletable.py [infile] [outdir] [flags...]
```
The output file will be written to `outdir` with a .rule extension and the same filename as `infile`.  
Supported flags:
  - `-v`: Verbose. Can be repeated up to four times, causing more info to be displayed each time.
  - `-c`: Comment. Writes each original rueltabel line as a comment above the line(s) it compiles
          to in the final output.
  - `-t [HEADER]`: Change the "COMPILED FROM RUELTABEL" header that is added by default to transpiled
                   rules. (If `-t` is given no argument the header will be removed)
  - `-f TRANSITION`: Find a certain transition defined within a tabel section; requires, of course, that
                     the rule have a `@TABEL` section to search within. Makes it so that, if a certain
                     cell isn't behaving the way it's supposed to, you can `-f` the transition it's
                     undergoing and the script will find the offending transition for you (instead of
                     making you guess at what you typo'd).  
                     Transition should be given in the standard Golly form `C,N,...,C'` -- that is, state of the
                     current center cell, then its neighborhood, and finally the state it transitions into
                     on the next tick. Example [here](https://user-images.githubusercontent.com/32081933/39951382-2b37fca0-553e-11e8-87b5-69685dfe4881.png)!  

## Spec
- All variables unbound by default, because needing to define eight "any state" vars is ridiculous.
- Support for `{}` literals, usable directly in transitions, as 'on-the-spot' variables. (Parentheses are also allowed. I personally prefer them to braces.)
- Support for cellstate *ranges* in variables, via double..dots as in `(0..8)` -- interspersible with state-by-state specification,
  so you can do `(0, 1, 4..6, 9)` to mean `(0, 1, 4, 5, 6, 9)`.
- Support for negation and subtraction of variables via the `-` and `--` operators:
```py
0, foo-bar, bar-2, bar-(2, 3), -1, --1, -bar, --(3, 4), (foo, bar), baz

# foo-bar says "All states in foo that are not in bar"
# foo-2 says "All states in foo that are not 2"
# bar-(2, 3) says "All states in bar that are not in (2, 3)"
# -1 says "All *live* states that are not 1" (expands to {2, 3, 4} assuming n_states==5)
# --1 says "*All* states (including 0) that are not 1" (expands to {0, 2, 3, 4} assuming the same)
# -bar and --(3, 4) say the same but with multiple states enclosed in a variable
```
Note that `--` can never be used between two variables; its only purpose is negation including state 0. `-`, however, is overloaded to mean both subtraction and negation-excluding-0.  
"Addition" of two variables can be accomplished by placing them in a variable literal, as in the final state above.
- Allow a variable to be made 'bound' by referring to its *index* in the transition, wrapped in [brackets]:  
```py
# current (barC repeats)
foo,barA,barB,barC,barD,barE,barF,barG,barH,barC
# new
foo,bar,bar,bar,bar,bar,bar,bar,bar,[3]

# current (barA repeats)
foo,barA,barB,barC,barA,barD,barE,barF,barG,baz
# new
foo,bar,bar,bar,[1],bar,bar,bar,bar,baz
```  
Transitions are zero-indexed from the input state and must refer to a previous index.
- To make binding even simpler, the reserved names `N NE E ... NW` are provided as symbolic constants for what the direction's index would be
  in the specified neighborhood. (The remainder of this document assumes the use of these constants rather than the raw indices,
  but they are interchangeable.)
- For example, in a rule with `neighborhood: vonNeumann`, the names `N E S W` are provided for `1 2 3 4`.
- This means that, above, the first 'new' transition can be rewritten as `foo,bar,bar,bar,bar,bar,bar,bar,bar,[E]` (E meaning east, because
  the 3rd `bar` represented the eastern cell), and the second as `foo,bar,bar,bar,[N],bar,bar,bar,bar,baz`.  
  (Note that the input state is still referred to as `[0]` — no symbolic name)
- Repetition can be cut down on even more by specifying directions directly before each state, which then allows
  *ranges* of directions (which of course ultimately map to their respective numbers). This means that the
  transitions above can be further rewritten to:
```py
# current (barC repeats)
foo,barA,barB,barC,barD,barE,barF,barG,barH,barC
# new
foo, N..NW bar, [E]

# current (barA repeats)
foo,barA,barB,barC,barA,barD,barE,barF,barG,baz
# new
foo, N..E bar, [N], S..NW bar, baz # could also be "..., SE [N], ..."
```
- A Golly-ruletable transition such as von-Neumann `0,a,a,a,a,1` might be inefficiently compacted to `0, a, [N], [N], [N], 1`, or worse
  `0, a, E..W [N], 1`. In such cases, where successive variables need all to be bound to the first, the shorthand `direction..direction [var]` can be used.
  Here it would look like `0, N..W [a], 1`, expanding during compilation to `0, a, [1], [1], [1], 1`.
- With this indexing, we can introduce "mapping" one variable to another. For instance, `foo, N..NW (0, 1, 2), [E: (1, 3, 4)]`
(meaning *map the eastern cell, being any of `(0, 1, 2)`, to the states `(1, 3, 4)`: if it's 0 return 1, if 1 return 3, if 2 return 4*) can
replace what would otherwise require a separate transition for each of `0`...`1`, `1`...`3`, and `2`...`4`.  
  Mapping of course works with named variables as well.
- If a variable literal is too small to map to, an error will be raised that can be rectified by either (a) filling it out with explicit transitions,
or (b) using the `...` operator to say *"fill the rest out with whatever value preceded the `...`"*.
- If the "map-to" is instead *larger* than its "map-from", extraneous values will simply be ignored.
- Treat live cells as moving objects: allow a cardinal direction to travel in and resultant cell state to be specified post transition.
```py
foo, N..NW bar, baz -> S:2 E[(2, 3)] SE[wutz] N[NE: (2, 3)] NE[E]

# S:2 says "spawn a state-2 cell to my south"

# E[(2, 3)] and SE[wutz] say "map this cell (E or SE) to this variable"

# N[NE: (2, 3)] says "spawn a cell to the north
# that maps the *northeastern* state variable to the (2, 3) literal."

# Be careful with this last syntax! You cannot, for example, write
# N[SE: (2, 3)] -- it implies a violation of the speed of light.
```
- Within these "post-transition cardinal direction specifiers" (referred to as "output specifiers", formerly "PTCDs"), the `_` keyword says "leave the cell as is".
- Allow transitions under permutational symmetry to make use of a shorthand syntax, specifying only the quantity of cells in each state. For example, `0,2,2,2,1,1,1,0,0,1`
  in a Moore+permute rule can be compacted to `0, 2*3, 1*3, 0*2, 1`.  
  Unmarked states will be filled in to match the number of cells in the transition's neighborhood, meaning
  that this transition can also be written as `0, 0*2, 1, 2, 1` or `0, 1*3, 2*3, 0, 1`.  
  - If the number of cells to fill is not divisible by the number of unmarked states, precedence will
    be given to those that appear earlier; `2,1,0`, for instance, will also expand into `2,2,2,1,1,1,0,0`, but `0,1,2` will expand into `0,0,0,1,1,1,2,2`.
- Support switching symmetries partway through via the `symmetries:` directive. (When parsing, this results in all transitions being expanded to the 'lowest'
symmetry type specified overall.)

## Non-table-related changes
- The `@COLORS` segment in a ruelfile allows multiple states with the same color to be defined as such
  on the same line as each other, and for colors to be written as either base-10 `R G B` values or as
  hexadecimal color codes. `1 10: FFF`, for instance, says to assign the color `#FFFFFF` to states 1 and
  10, and can also be written as `1 10: FFFFFF` or `1 10: 255 255 255` (or as two separate lines, although
  the colon is still mandatory). Comments in this segment start with `#` and go until the end of their line.
- The `@ICONS` segment uses an ad-hoc RLE syntax instead of Gollyesque XPM data. See [this post](http://conwaylife.com/forums/viewtopic.php?f=7&t=3361&p=59944#p59944)
  for an explanation + example.
- **All segments are optional**. The parser will also transcribe unidentified segments as is, meaning that
  a file can have a `@TABLE` segment (under which the normal Golly ruletable language is used) rather than
  `@TABEL` and it will not be modified by the parser.
- Specially-treated ruel segments whose names are not respellings, like `@ICONS` and `@COLORS`, will still be
  ignored by the parser if their header is immediately followed by the comment `#golly`, either on the same line (after whitespace) or on the line immediately below.

## To do
- DOCS! Or at least a proper introductory writeup.
- Do something (???) to attempt to simplify permutationally-symmetric transitions such as in TripleLife.

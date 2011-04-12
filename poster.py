'''\
Generate an SVG poster of Unicode characters.
'''

from optparse import OptionParser
from pprint import pprint
import sys
import icu

scripts = (
    'Latn',
    'Cyrl',
    'Hebr',
    'Arab',
    'Deva',
    'Bali',
)

# just use the default locale's ordering
collator = icu.Collator.createInstance()

def get_characters():
    '''\
    Returns an iterable of codepoints, in order.
    '''
    
    assigned = set(icu.UnicodeSet("[[:^gc=Cn:]]")) # all assigned characters
    space = set(icu.UnicodeSet("[[:gc=Z:]]"))
    control = set(icu.UnicodeSet("[[:gc=C:]]"))
    admissible = assigned - (space | control)
    
    chars = set()
    for sc in scripts:
        script = set(icu.UnicodeSet("[[:sc=%s:]]" % sc)) & admissible
        chars |= script
    
    result = list(chars)
    result.sort(cmp=collator.compare)
    
    return result

def render_cell(character):
    return character

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option(
        '-u', '--ucd',
        dest= 'ucd',
        help= "path of the Unicode Character Database to use. defaults to 'ucd'.",
        default="ucd",
    )
    parser.add_option(
        '-o', '--outfile',
        dest= 'outfile',
        help= "output the poster as FILE. defaults to STDOUT.",
        metavar="FILE",
    )
    (options, args) = parser.parse_args()
    
    if options.outfile is None:
        out = sys.stdout
    else:
        out = open(options.outfile)
    
    for c in get_characters():
        out.write(render_cell(c).encode('utf-8') + ' ')
    
    out.write('\n')


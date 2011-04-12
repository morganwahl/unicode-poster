'''\
Generate an SVG poster of Unicode characters.
'''

from optparse import OptionParser
from pprint import pprint
import sys

import icu

from lxml import etree

scripts = (
    'Goth',
)

# just use the default locale's ordering
collator = icu.Collator.createInstance()

def get_characters():
    '''\
    Returns an iterable of codepoints, in order.
    '''
    
    assigned = set(icu.UnicodeSet("[[:^gc=Cn:]]")) # all assigned characters
    space = set(icu.UnicodeSet("[[:gc=Z:]]"))
    control = set(icu.UnicodeSet("[[:gc=C:]]")) # includes control, surrogates, private use and formatting
    decomposible = set(icu.UnicodeSet("[[:Decomposition_Type=Canonical:]]"))
    admissible = assigned - (space | control | decomposible)
    
    chars = set()
    for sc in scripts:
        script = set(icu.UnicodeSet("[[:sc=%s:]]" % sc)) & admissible
        chars |= script
    
    result = []
    
    for c in chars:
        # Collator gets indigestion on certain non-BMP python unicode objects
        uni_c = icu.UnicodeString(c.encode('utf-8'))
        try:
            key = collator.getCollationKey(c.encode('utf-8'))
        except icu.ICUError:
            pprint((c, uni_c))
            sys.exit(1)
        result.append(uni_c)
    
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
    
    svg = etree.Element("svg", width="1024", height="500")
    
    for c in get_characters():
        group = etree.SubElement(svg, "g")
        text = etree.SubElement(group, "text")
        text.text = unicode(c)
    
    out.write(etree.tostring(svg, pretty_print=True, xml_declaration=True, encoding='utf-8'))
    

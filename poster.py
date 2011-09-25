'''\
Generate an SVG poster of Unicode characters.
'''

from optparse import OptionParser
from pprint import pprint
import sys

import icu

from lxml import etree

SVG_NAMESPACE = 'http://www.w3.org/2000/svg'

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
    parser.add_option(
        '-w', '--width',
        dest= 'width',
        help= "width of the SVG image. defaults to 72in",
        default= unicode(6 * 12) + "in" # 6 feet
    )
    parser.add_option(
        '-t', '--height',
        dest= 'height',
        help= "height of the SVG image. defaults to 36in",
        default= unicode(3 * 12) + "in" # 3 feet
    )
    (options, args) = parser.parse_args()
    
    if options.outfile is None:
        out = sys.stdout
    else:
        out = open(options.outfile)
    
    SVG = "{%s}" % SVG_NAMESPACE
    NSMAP = {
        None: SVG_NAMESPACE,
    }
    
    svg = etree.Element(SVG + "svg", nsmap=NSMAP, width=options.width, height=options.height, version="1.1")
    
    chars = get_characters()
    # figure out the cell-size, given the poster size, number of cells,
    # and a 3:4 aspect ratio for the cells.
    #
    # cell height: ch
    # cell width: cw
    # poster height: ph
    # poster width: pw
    # # of rows = r
    # # of columns = c
    # # of cells = n
    # 
    # cw / ch = 4 / 3
    # ceil(n / c) = r
    # r * ch  = ph
    # c * cw = pw
    #
    # cw = (4 * ch) / 3
    # (4 * c * ch) / 3  = pw
    # (4 * ch) / 3 = pw / c
    # 3 / (4 * ch) = c / pw
    # (3 * pw) / (4 * ch) = c = (3/4) * (pw/ch)
    # c = (3/4) * (pw/(ph/r)) = (3/4) * ((pw * r)/ph)
    
    for c in chars:
        group = etree.SubElement(svg, SVG + "g")
        text = etree.SubElement(group, SVG + "text")
        text.text = unicode(c)
    
    out.write(etree.tostring(svg, pretty_print=True, xml_declaration=True, encoding='utf-8'))
    

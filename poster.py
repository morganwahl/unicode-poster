'''\
Generate an SVG poster of Unicode characters.
'''

from collections import namedtuple
from decimal import Decimal as D
from decimal import ROUND_UP, ROUND_DOWN
from optparse import OptionParser
from pprint import pprint
import re
import sys

from lxml import etree, objectify

SVG_NAMESPACE = 'http://www.w3.org/2000/svg'

POSTER_HEIGHT = D(3) * 12 * 300
#POSTER_HEIGHT = D(1000)
CELL_ASPECT = (D(3), D(4))
ROWS = 175
#ROWS = 20
CELL_HEIGHT = POSTER_HEIGHT / ROWS
CELL_WIDTH = (CELL_HEIGHT / CELL_ASPECT[1]) * CELL_ASPECT[0]

UCD_PATH = "../ucd/ucd.all.flat.xml"
DUCET_PATH = "../ucd/allkeys.txt"

SVG_NAMESPACE = 'http://www.w3.org/2000/svg'

scripts = (
    'Arab',
    'Latn',
    'Hebr',
    'Grek',
    'Zyyy',
)

class UCDTarget(object):
    '''\
    An lxml target for parsing the UCD in XML. Produces a dictionary keyed to
    numeric codepoints.
    '''
    
    UCD_NS = 'http://www.unicode.org/ns/2003/ucd/1.0'
    UCD = '{%s}' % UCD_NS
    Char = namedtuple('char', 'dt gc sc ducet_key')
    
    def __init__(self):
        self.parents = []
        self.u = [None] * 0x10ffff
    
    @staticmethod
    def derive_weight(cp, UIdeo):
        base = 0xfbc0
        if UIdeo:
            # from Blocks.txt in UCD 6.0.0
            # 4E00..9FFF; CJK Unified Ideographs
            # F900..FAFF; CJK Compatibility Ideograph
            # TODO we want to store each character as we come across it, but
            # blocks are stored after characters in the UCD file, so these
            # two blocks are just hard-coded. They should never change, though.
            #if blk in ('CJK_Unified_Ideographs', 'CJK_Compatibility_Ideographs'):
            if (cp >= 0x4e00 and cp <= 0x9fff) or (cp >= 0xf900 and cp <= 0xfaff):
                base = 0xfb40
            else:
                base = 0xfb80
        
        aaaa = base + (cp >> 15)
        bbbb = (cp & 0x7fff) | 0x8000;
        
        ducet_key = ("%04X" * 6) % (
            aaaa,
            bbbb,
            0x20,
            0,
            0x2,
            0,
        )
        
        return ducet_key
    
    def process_char(self, codepoint, attributes):
        try:
            UIdeo = attributes['UIdeo']
        except KeyError:
            pprint((codepoint, attributes))
            sys.exit()
        props = self.Char(
            attributes['dt'],
            attributes['gc'],
            attributes['sc'],
            self.derive_weight(codepoint, UIdeo),
        )
        self.u[codepoint] = props
    
    def data(self, data):
        if self.parents == [
            self.UCD + 'ucd',
            self.UCD + 'description',
        ]:
            print "Parsing UCD described as: \"%s\"" % data
    
    def start(self, tag, attrib):
        if tag == self.UCD + 'char' and self.parents == [
            self.UCD + 'ucd',
            self.UCD + 'repertoire',
        ]:
            if 'cp' in attrib:
                cp = int(attrib['cp'], 0x10)
                self.process_char(cp, attrib)
            elif 'first-cp' in attrib and 'last-cp' in attrib:
                for cp in range(int(attrib['first-cp'], 0x10), int(attrib['last-cp'], 0x10) + 1):
                    self.process_char(cp, attrib)
            else:
                pprint(attrib)
                raise Exception("Can't figure out char entry!")
        self.parents.append(tag)
    
    def end(self, tag):
        if tag != self.parents[-1]:
            raise Exception("Malformed XML! Got </%s>, was expecting </%s>." % (tag, self.parents[-1]))
        self.parents.pop()
    
    def close(self):
        return self.u

# add collation keys from the DUCET
def _add_uca_keys():
    "reading DUCET from %s" % DUCET_PATH
    ducet = open(DUCET_PATH)
    for line in ducet:
        original_line = line
        # strip comments
        line = line.split('#', 1)[0]
        line = line.split('%', 1)[0]
        # trim whitespace
        line = line.strip()
        # skip blanks
        if not line:
            continue
        
        if line[0] == '@':
            version_match = re.search(r'^@version\s*([^.]*)\.([^.]*)\.([^.]*)$', line)
            if version_match:
                (major, minor, variant) = version_match.groups()
                print "Reading DUCET version %s.%s.%s" % (major, minor, variant)
                continue
            
            other_match = re.search(r'^@(variable|backwards|forwards)', line)
            if other_match:
                raise Exception("This script can't process a DUCET file with a '%s' directive!" % other_match.group(0))
            
            # line starts with '@' but isn't understood
            raise Exception("Unrecognized directive %s!" % re.search(r'^@(.*)$', line).group(0))
        
        # TODO check that line matches a regex summarizing the assumptions below
        
        chars, keys = line.split(';', 1)
        
        chars = chars.strip()
        chars = chars.split()
        chars = map(lambda x: int(x, 0x10), chars)
        
        # we don't care about multi-char entries
        if len(chars) > 1:
            continue
        char = chars[0]
        
        keys = keys.strip()
        keys = keys[1:-1] # remove the trailing and leading '[' and ']'
        keys = keys.split('][')
        keys = map(
            lambda k: {
                'alt': k[0],
                'weights': map(
                    #lambda w: int(w, 0x10),
                    lambda w: w,
                    k[1:].split('.'),
                ),
            },
            keys,
        )
        # we don't care about variable weighting, so the 'alt' doesn't matter
        
        sort_key = ''
        max_level = 0
        for k in keys:
            max_level = max(max_level, len(k['weights']))
        for l in range(max_level):
            for k in keys:
                sort_key += k['weights'][l]
        
        UCD[char] = UCDTarget.Char(
            UCD[char].dt,
            UCD[char].gc,
            UCD[char].sc,
            sort_key,
        )
        
    ducet.close()

print "parsing UCD from %s" % UCD_PATH

ucd_parser = etree.XMLParser(target=UCDTarget())
UCD = etree.XML(open(UCD_PATH).read(), ucd_parser)
_add_uca_keys()

def icu_get_characters():
    '''\
    Returns an iterable of codepoints, in order.
    '''
    
    import icu

    print "using ICU for Unicode version %s" % icu.UNICODE_VERSION

    # just use the default locale's ordering
    collator = icu.Collator.createInstance()

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
    
    for c in admissible:
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

def ucd_get_characters():
    
    result = []
    
    for p in range(len(UCD)):
        props = UCD[p]
        if props is None:
            continue
        # skip unassigned, control, surrogate, formatting, and private-use
        # characters
        if props.gc[0] == 'C':
            continue
        # skip space characters
        if props.gc[0] == 'Z':
            continue
        # skip canonically decomposible characters
        if props.dt == 'can':
            continue
        # skip scripts we don't care about
        if props.sc not in scripts:
            continue
        
        result.append(unichr(p))
    
    result.sort(key=lambda c: UCD[ord(c[0])].ducet_key)
    
    return result

get_characters = ucd_get_characters

def add_cell(character, group):
    point = ord(character[0])

    if UCD[point].dt != 'none':
        dt = etree.SubElement(group, SVG + 'text',
            x= unicode(.2),
            y= unicode(.6),
            fill= "grey",
        )
        dt.set('font-size', '.5')
        dt.set('font-family', 'sans-serif')
        dt.set('text-anchor', 'start')
        dt.text = UCD[point].dt
        
        strike = etree.SubElement(group, SVG + 'line',
            x1= "3",
            y1= "0",
            x2= "0",
            y2= "3",
            stroke= "lightgrey",
        )
        strike.set('stroke-width', '.05')

    line = etree.SubElement(group, SVG + "line",
        x1="0",
        y1="3",
        x2="3",
        y2="3",
        stroke="lightgrey",
    )
    line.set('stroke-width', '.05')
    #dot = etree.SubElement(group, SVG + "circle",
    #    cx="1.5",
    #    cy="2",
    #    r=".1",
    #    fill="red",
    #)

    text = etree.SubElement(group, SVG + "text",
        x="1.5",
        y="2",
    )
    text.set('font-size', '2')
    text.set('text-anchor', 'middle')
    text.text = unicode(character)

    rect = etree.SubElement(group, SVG + "rect",
        x="0",
        y="0",
        width="3",
        height="4",
        fill="none",
        stroke="grey",
    )
    rect.set('stroke-width', '.1')

    cp = etree.SubElement(group, SVG + 'text',
        x= unicode(1.5),
        y= unicode(3 - .2),
        fill= "grey",
    )
    cp.set('font-size', '.5')
    cp.set('font-family', 'monospace')
    cp.set('text-anchor', 'middle')
    pad = '4'
    if point > 0xffff:
        pad = '6'
    cp.text = ('%0' + pad + 'X') % point

    gc = etree.SubElement(group, SVG + 'text',
        x= unicode(0 + .2),
        y= unicode(4 - .2),
    )
    gc.set('font-size', '.5')
    gc.set('font-family', 'sans-serif')
    gc.set('text-anchor', 'start')
    gc.text = UCD[point].gc
    
    sc = etree.SubElement(group, SVG + 'text',
        x= unicode(3 - .2),
        y= unicode(4 - .2),
    )
    sc.set('font-size', '.5')
    sc.set('font-family', 'sans-serif')
    sc.set('text-anchor', 'end')
    sc.text = UCD[point].sc
    
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
        out = open(options.outfile, 'wb')
    
    SVG = "{%s}" % SVG_NAMESPACE
    NSMAP = {
        None: SVG_NAMESPACE,
    }
    
    chars = get_characters()

    characters = D(len(chars))
    
    height = POSTER_HEIGHT
    rows = ROWS
    columns = (characters / rows).quantize(1, rounding=ROUND_UP)
    width = (columns * CELL_WIDTH).quantize(1, rounding=ROUND_UP)
    area = width * height
    cell_width = CELL_WIDTH
    cell_height = CELL_HEIGHT
    cell_area = CELL_WIDTH * CELL_HEIGHT
    
    print "poster: %d x %d = %d" % (width, height, area)
    print "poster: %d' x %d'" % (width / (12 * 300), height / (12 * 300))
    print "cell: %f x %f = %f" % (cell_width, cell_height, cell_area)
    print "chars: %d x %d = %d, %d" % (columns, rows, columns * rows, len(chars))
    print "width: %d x %f = %f, %d" % (columns, cell_width, cell_width * columns, width)
    print "height: %d x %f = %f, %d" % (rows, cell_height, cell_height * rows, height)
    
    svg = etree.Element(SVG + "svg",
        nsmap=NSMAP,
        width=unicode(width),
        height=unicode(height),
        version="1.1",
    )
    
    # white background
    etree.SubElement(svg, SVG + "rect", width="100%", height="100%", fill="white")
    
    row = 0
    col = 0
    scaling = "scale(%f,%f)" % (
        cell_width / CELL_ASPECT[0],
        cell_height / CELL_ASPECT[1],
    )
    cells = etree.SubElement(svg, SVG + "g", transform=scaling)
    for c in chars:
        translation = "translate(%f,%f)" % (
            col * CELL_ASPECT[0],
            row * CELL_ASPECT[1],
        )
        group = etree.SubElement(cells, SVG + "g", transform=translation)
        add_cell(c, group)
        
        col += 1
        if col == columns:
            col = 0
            row += 1
    
    out.write(etree.tostring(svg, pretty_print=True, xml_declaration=True, encoding='utf-8'))
    

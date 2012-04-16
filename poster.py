#!/usr/bin/python

'''\
Generate a poster of Unicode characters.
'''

from decimal import Decimal as D
from decimal import ROUND_UP, ROUND_DOWN
from optparse import OptionParser
from pprint import pprint
import re
import sys
import pickle

import cairo
import pango
import pangocairo

from lxml import etree, objectify

UCD_CACHE_PATH = 'ucd-cache'

INCH = D('300')
POINT = INCH / D(72) # postscript DPI
POSTER_HEIGHT = D(8) * INCH
#POSTER_HEIGHT = D(1000)
CELL_ASPECT = (D(3), D(4))
ROWS = (POSTER_HEIGHT / (D('.25') * INCH)).quantize(1, rounding=ROUND_DOWN) # each cell will be at least 1/2" tall
#ROWS = 20
CELL_HEIGHT = POSTER_HEIGHT / ROWS
CELL_WIDTH = (CELL_HEIGHT / CELL_ASPECT[1]) * CELL_ASPECT[0]

#GENERIC_BASE = u"\u25cc"
GENERIC_BASE = u""

UCD_PATH = "../ucd/ucd.all.flat.xml"
DUCET_PATH = "../ucd/allkeys.txt"

SCRIPTS = (
    #"Xsux Xpeo Ugar Egyp", # 0xx

    #"Sarb", # 10x
    #"Phnx Lydi", # 11x
    #"Tfng Samr Armi Hebr", # 12x
    #"Prti Phli Avst Syrc", # 13x
    #"Mand Mong", # 15x
    #"Arab Nkoo", # 16x
    #"Thaa Orkh", # 17x

    #"Grek Cari Lyci Copt Goth", # 20x
    "Ital Runr Ogam Latn", # 21x
    #"Cyrl Glag", # 22x
    #"Armn", # 23x
    #"Geor", # 24x
    #"Dsrt", # 25x
    #"Osma Olck", # 26x
    #"Shaw Bopo Hang", # 28x

    #"Brah Khar", # 30x
    #"Guru Deva Sylo Kthi", # 31x
    #"Gujr Beng Orya", # 32x
    #"Tibt Phag Lepc Limb Mtei", # 33x
    #"Telu Saur Knda Taml Mlym Sinh", # 34x
    #"Mymr Lana Thai Tale Talu Khmr Laoo Kali Cham Tavt", # 35x
    #"Bali Java Sund Rjng Batk Bugi", # 36x
    #"Tglg Hano Buhd Tagb", # 37x
    #"Lisu", # 39x
    
    #"Linb Cprt Hira Kana Hrkt Ethi Bamu Cans Cher Yiii Vaii", # 4xx
    
    #"Hani Brai", # 5xx
    
    #"Zinh Zyyy", # 9xx
)

SCRIPTS = ' '.join(SCRIPTS).strip().split()

class Char(object):
    
    def __init__(self, ccc, dt, gc, sc, ducet_key=None):
        self.ccc = ccc
        self.dt = dt
        self.gc = gc
        self.sc = sc
        self.ducet_key = ducet_key

class UCDTarget(object):
    '''\
    An lxml target for parsing the UCD in XML. Produces a dictionary keyed to
    numeric codepoints.
    '''
    
    UCD_NS = 'http://www.unicode.org/ns/2003/ucd/1.0'
    UCD = '{%s}' % UCD_NS
    
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
        props = Char(
            attributes['ccc'],
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
def _add_uca_keys(UCD):
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
        
        UCD[char] = Char(
            UCD[char].ccc,
            UCD[char].dt,
            UCD[char].gc,
            UCD[char].sc,
            sort_key,
        )
        
    ducet.close()

def parse_ucd():

    ucd_data = None
    try:
        with open(UCD_CACHE_PATH, 'rb') as ucd_cache:
            print "reading cached UCD data...",
            sys.stdout.flush()
            ucd_data = pickle.load(ucd_cache)
            print " done!"
    except IOError:
        print "can't read existing UCD cache file"
    except EOFError:
        print "can't read existing UCD cache file"
    
    if ucd_data is None:
        print "parsing UCD from %s" % UCD_PATH

        ucd_parser = etree.XMLParser(target=UCDTarget())
        ucd_data = etree.XML(open(UCD_PATH).read(), ucd_parser)
        _add_uca_keys(ucd_data)
        
        with open(UCD_CACHE_PATH, 'wb') as ucd_cache:
            print "caching UCD data in '%s'" % UCD_CACHE_PATH
            pickle.dump(ucd_data, ucd_cache, pickle.HIGHEST_PROTOCOL)

    return ucd_data

def ucd_get_characters(UCD):
    
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
        if not SCRIPTS is None:
            if props.sc not in SCRIPTS:
                continue
        
        result.append(unichr(p))
    
    result.sort(key=lambda c: UCD[ord(c[0])].ducet_key)
    
    return result

def draw_small_cell(character, cairo_context):
    c, cr = character, cairo_context
    pcr = pangocairo.CairoContext(cr)
    
    point = ord(character[0])
    if UCD[point].ccc != 0:
        character = GENERIC_BASE + character
    
    cr.set_source_rgb(0, 0, 0)
    
    if UCD[point].dt != 'none':
        #dt = etree.SubElement(group, SVG + 'text',
        #    x= unicode(.2),
        #   y= unicode(.6),
        #    fill= "#888888",
        #)
        #dt.set('font-size', '.5')
        #dt.set('font-family', 'sans-serif')
        #dt.set('text-anchor', 'start')
        #dt.text = UCD[point].dt

        cr.save()
        cr.set_line_width(.05)
        cr.set_source_rgb(.6, .6, .6)
        cr.new_path()
        cr.move_to(3, 0)
        cr.line_to(0, 4)
        cr.stroke()
        cr.restore()

    cr.save()
    cr.set_line_width(.1)
    cr.set_source_rgb(.6, .6, .6)
    cr.rectangle(0, 0, 3, 4)
    cr.stroke()
    cr.restore()

    cr.save()
    text = pcr.create_layout()
    text.set_font_description(pango.FontDescription('2'))
    text.set_alignment(pango.ALIGN_CENTER)
    text.set_width(-1)
    text.set_text(character)
    w, h = text.get_size()
    w = D(w) / D(pango.SCALE)
    h = D(h) / D(pango.SCALE)
    if w * h > (3 * 4) * D(2):
        #pprint(("big character", point, character, w, h, w * h))
        pass
    else:
        cr.move_to(D('1.5') - (w / 2), 2 - (h / 2))
        pcr.show_layout(text)
    cr.restore()
    
    #gc = etree.SubElement(group, SVG + 'text',
    #    x= unicode(0 + .2),
    #    y= unicode(4 - .2),
    #    fill= "#888888",
    #)
    #gc.set('font-size', '.5')
    #gc.set('font-family', 'sans-serif')
    #gc.set('text-anchor', 'start')
    #gc.text = UCD[point].gc
    cr.save()
    cr.set_source_rgb(.4, .4, .4)
    gc = pcr.create_layout()
    gc.set_font_description(pango.FontDescription('Sans .5'))
    gc.set_alignment(pango.ALIGN_LEFT)
    gc.set_width(-1)
    gc.set_text(UCD[point].gc)
    w, h = gc.get_size()
    w = D(w) / D(pango.SCALE)
    h = D(h) / D(pango.SCALE)
    cr.move_to((0 + D('.1')), (4 - D('.1')) - h)
    pcr.show_layout(gc)
    cr.restore()
    
    cr.save()
    cr.set_source_rgb(.4, .4, .4)
    sc = pcr.create_layout()
    sc.set_font_description(pango.FontDescription('Sans .5'))
    sc.set_alignment(pango.ALIGN_RIGHT)
    sc.set_width(-1)
    sc.set_text(UCD[point].sc)
    w, h = sc.get_size()
    w = D(w) / D(pango.SCALE)
    h = D(h) / D(pango.SCALE)
    cr.move_to((3 - D('.1')) - w, (0 + D('.1')))
    pcr.show_layout(sc)
    cr.restore()

    cr.save()
    cr.set_source_rgb(.4, .4, .4)
    cp = pcr.create_layout()
    cp.set_font_description(pango.FontDescription('Monospace .4'))
    cp.set_alignment(pango.ALIGN_RIGHT)
    cp.set_width(-1)
    pad = '4'
    if point > 0xffff:
        pad = '6'
    cp.set_text((u'%0' + pad + 'X') % point)
    w, h = cp.get_size()
    w = D(w) / D(pango.SCALE)
    h = D(h) / D(pango.SCALE)
    cr.move_to((3 - D('.1')) - w, (4 - D('.1')) - h)
    pcr.show_layout(cp)
    cr.restore()

def render_cairo(out, chars, width, height, cell_width, cell_height):
    
    s = cairo.PDFSurface(out, width / POINT, height / POINT)
    
    cr = cairo.Context(s)
    # scale to pixels
    cr.scale(1 / POINT, 1 / POINT)
    
    # white background
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    
    row = 0
    col = 0
    cr.scale(
        cell_width / CELL_ASPECT[0],
        cell_height / CELL_ASPECT[1],
    )
    for i, c in enumerate(chars):
        if not i % 1000:
            print "%d%%" % (i * 100.0 / len(chars))
        cr.save()
        cr.translate(
            col * CELL_ASPECT[0],
            row * CELL_ASPECT[1],
        )
        draw_small_cell(c, cr)
        cr.restore()
        
        col += 1
        if col == columns:
            col = 0
            row += 1

render = render_cairo

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
        help= "output the poster as FILE. defaults to 'all.pdf'.",
        metavar="FILE",
    )
    (options, args) = parser.parse_args()
    
    filename = options.outfile
    if options.outfile is None:
        filename = 'all.pdf'
    out = open(filename, 'wb')
    
    UCD = parse_ucd()

    chars = ucd_get_characters(UCD)

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
    print "poster: %d\" x %d\" = %f sq/ ft." % (width / INCH, height / INCH, (width * height) / ((12 ** 2) * (INCH ** 2)))
    print "cell: %f x %f = %f" % (cell_width, cell_height, cell_area)
    print "chars: %d x %d = %d, %d" % (columns, rows, columns * rows, len(chars))
    print "width: %d x %f = %f, %d" % (columns, cell_width, cell_width * columns, width)
    print "height: %d x %f = %f, %d" % (rows, cell_height, cell_height * rows, height)
    
    render(out, chars, width, height, cell_width, cell_height)
    
    out.close()
    

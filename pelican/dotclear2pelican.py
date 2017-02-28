#!/usr/bin/env python3
# -*- encoding: UTF-8 -*-

import os, sys, unicodedata, re
import psycopg2
import psycopg2.extras
import pypandoc

DOTCLEAR_SERVER = '*******'
DOTCLEAR_USER = '*******'
DOTCLEAR_DB = '*******'
DOTCLEAR_PWD = '*******'
OUTPUT_DIR = '*******'
INPUT_FORMAT = 'textile'
OUTPUT_FORMAT = 'rst'

V1_MEDIA = re.compile(r'https://media.lordran.net/alpha/posts/(.*)')
V1_REP = r'{filename}/images/v1/\1'
V2_MEDIA = re.compile(r'https://old-alpha.lordran.net/public/(.*)')
V2_REP = r'{filename}/images/v2/\1'

BAD_SMILEY = re.compile(r' :sup:``[;"]')
FIX_SMILEY = r'.'

BAD_NBSP = '   '

BAD_IMGLINK = re.compile(r'\|([^\|]+)\|:(\{filename\}/images/[-_/\\a-zA-Z0-9\.]+)')

def suppression_diacritics(s):
    def remove(char):
        deco = unicodedata.decomposition(char)
        if deco:
            for c in deco.split():
                try:
                    return chr(int(c, 16))
                except ValueError:
                    pass
        return char

    return u''.join([remove(a) for a in s])

def slugify(value):
    "Converts to lowercase, removes diacritics marks and converts spaces to hyphens"
    value = suppression_diacritics(value)
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value).strip('-')

with psycopg2.connect(dbname=DOTCLEAR_DB, user=DOTCLEAR_USER, password=DOTCLEAR_PWD, host=DOTCLEAR_SERVER) as conn:
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute('SELECT post_dt, post_upddt, post_title, post_excerpt, post_content, post_status, cat_title FROM dc_post NATURAL INNER JOIN dc_category ORDER BY post_dt')

        for row in cur.fetchall():
            filename = '{}_{}.rst'.format(row['post_dt'].isoformat(), slugify(row['post_title']))
            #cat_slug = slugify(row['cat_title'])
            cat_slug = row['cat_title']

            # Create category block
            cat_path = os.path.join(OUTPUT_DIR, cat_slug)
            if not os.path.exists(cat_path):
                os.makedirs(cat_path)

            filepath = os.path.join(cat_path, filename)
            print(filepath)
            with open(filepath, 'w') as fh:
                # Title
                print(row['post_title'], file=fh)
                print('#' * len(row['post_title']), file=fh)
                print(file=fh)

                # Date
                print(':date:', row['post_dt'].isoformat(), file=fh)
                print(':modified:', row['post_upddt'].isoformat(), file=fh)

                print(':category:', row['cat_title'], file=fh)
                print(':slug:', slugify(row['post_title']), file=fh)
                print(':author: Johann', file=fh)
                print(':lang: fr', file=fh)
                if row['post_status'] == 1:
                    print(':status: published', file=fh)
                else:
                    print(':status: draft', file=fh)
                print(file=fh)

                output = pypandoc.convert_text(row['post_excerpt'] + "\n\n" + row['post_content'], \
                        OUTPUT_FORMAT, format=INPUT_FORMAT)

                output = V1_MEDIA.sub(V1_REP, output)
                output = V2_MEDIA.sub(V2_REP, output)
                output = BAD_SMILEY.sub(FIX_SMILEY, output)

                f_output = []
                for line in output.split('\n'):
                    if line == BAD_NBSP:
                        continue
                    f_output.append(line)
                output = '\n'.join(f_output).strip()

                # Patch Totoro
                output = output.replace(' o\_o', '')

                idx_imglinks = []
                for match in BAD_IMGLINK.finditer(output):
                    idx_imglinks.append({'tag': match.group(1), 'url': match.group(2)})
                    output = output.replace('|{}|:{}'.format(match.group(1), match.group(2)),
                            '|{}|_'.format(match.group(1)))

                print(output, file=fh)

                for imglink in idx_imglinks:
                    print(".. _{}: {}".format(imglink['tag'], imglink['url']), file=fh)

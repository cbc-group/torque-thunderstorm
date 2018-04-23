import argparse
import os
import csv
import re
import operator
import sqlite3 as sql
from math import sin, cos, radians
import time

TABLE_NAME = 'particles'

# default values
DEFAULT_OUTPUT = 'merged.csv'
DEFAULT_REGEX = '.*layer_(\d+).*\.csv'

FLOAT_COMPILED_REGEX = re.compile('\d+(\.\d+)?')

# template has header names as keys, with a tuple of (unit, sql type) as values
HEADER_LUT = {
    'frame':            ('', 'INTEGER'),
    'x':                ('[nm]', 'REAL'),
    'y':                ('[nm]', 'REAL'),
    'z':                ('[nm]', 'REAL'),
    'sigma':            ('[nm]', 'REAL'),
    'sigma1':           ('[nm]', 'REAL'),
    'sigma2':           ('[nm]', 'REAL'),
    'intensity':        ('[nm]', 'REAL'),
    'offset':           ('[nm]', 'REAL'),
    'bkgstd':           ('[nm]', 'REAL'),
    'uncertainty_xy':   ('[nm]', 'REAL'),
    'uncertainty_z':    ('[nm]', 'REAL')
}

def patch_z(row, dim, z):
    '''
    Patch 2D data with an additional Z column.

    Arguments
    ---------
        row         the actual entry
        dim         dimension of the dataset
        z           depth (nm)
    '''
    if dim == 2:
        # append the column since that column doesn't exist yet
        row.append(str(z))
    elif dim == 3:
        pass
    else:
        # ERROR
        pass

    return row

def shear(col_num, row, dim, z, angle):
    '''
    Shear the coordinate if angle is greater than 0.

    Arguments
    ---------
        col_num     list that contains the column positions
        row         the actual entry
        interval    distance between each layers
        angle       shearing angle in degrees
    '''
    if angle > 0:
        x_col_num = col_num['x']
        x = float(row[x_col_num])

        # TODO: use decorator pattern to avoid running the sin, cos
        # mutliple times.
        angle = radians(angle)

        x += z*sin(angle)
        # update corrected x
        row[x_col_num] = str(x)

        z *= cos(angle)
        row = recalc_z(col_num, row, dim, z)

    return row

def recalc_z(col_num, row, dim, z):
    '''
    Reprocess the depth value, add the offset if incoming data is 3D.

    Arguments
    ---------
        col_num     list that contains the column positions
        row         the actual entry
        dim         dimension of the dataset
        z           depth (nm)
    '''
    z_col_num = col_num['z']

    if dim == 2:
        pass
    elif dim == 3:
        z_offset = float(row[z_col_num])
        z = z-z_offset

    row[z_col_num] = str(z)

    return row

def is_valid(col_num, row):
    '''
    Validate the row entry by xy/z uncertainty.

    Arguments
    ---------
        col_num     list that contains the column positions
        row         entry that required validation
    '''
    uncert_z_col_num = col_num.get('uncertainty_z')
    if uncert_z_col_num:
        col_str = row[uncert_z_col_num]
        # only 3D data has Z uncertainty value
        return FLOAT_COMPILED_REGEX.match(col_str) != None
    else:
        return True

def load_csv(path):
    with open(path, 'r') as f:
        reader = csv.reader(f, delimiter=',')

        #skip the header
        next(reader)
        # iterate through the lines
        for row in reader:
            yield row

def find_layer_num(fname, regex):
    match = re.search(regex, fname)
    if not match or len(match.groups()) > 1:
        # Error
        pass
    else:
        return float(match.group(1))

def find_col_num(path, lut=HEADER_LUT):
    '''
    Parse the position of the columns using a template header.

    Arguments
    ---------
        path        path to the CSV file for parsing
        lut         lookup table for the header information
    '''
    with open(path, 'r') as f:
        reader = csv.reader(f, delimiter=',')

        # retrieve the heaer
        header = next(reader)

        # generate the dictionary based on valid column names
        d = dict()
        key_tpl = lut.keys()
        for i, col in enumerate(header):
            # split the unit
            try:
                key, unit = col.split()
            except:
                key = col
                unit = ''

            # verify the key is in the template
            if key not in key_tpl:
                # Error
                pass

            # verify the unit match
            if lut[key][0] != unit:
                # Error
                pass

            d[key] = i
            i += 1

    return d

def init_db(db_path, col_num, lut=HEADER_LUT):
    '''
    Initialize the sqlite3 database using CSV input column types. A file storage
    and an in-memory storage are created and attached together.

    Arguments
    ---------
        csv_path    path to the template .csv file
        db_path     path to store the .db file
    '''
    conn = sql.connect(db_path)
    cur = conn.cursor()

    # remove the original table to avoid complications
    cur.execute('DROP TABLE IF EXISTS main.{}'.format(TABLE_NAME))

    # build the sql header
    col_num_sort = sorted(col_num.items(), key=operator.itemgetter(1))
    col = [key[0] + ' ' + lut[key[0]][1] for key in col_num_sort]
    cur.execute('CREATE TABLE {} ({})'.format(TABLE_NAME, ','.join(col)))
    conn.commit()

    # duplicate the structure to in-memory database
    cur.execute('ATTACH DATABASE \'{}\' AS tmp'.format(':memory:'))
    cur.execute('CREATE TABLE tmp.{0} AS SELECT * FROM main.{0}'.format(TABLE_NAME))

    conn.commit()

    return conn, cur

def main(regex, angle, interval, src_dir, out_path):
    # search all valid CSV files
    file_list = [
        os.path.join(src_dir, f)
        for f in os.listdir(src_dir)
        if f.endswith('.csv')
    ]
    n_files = len(file_list)
    print(' * {} file(s) are found in the folder'.format(n_files))

    # identify input type
    col_num = find_col_num(file_list[0])
    # patch the z column back if we are working with 2D raw data
    if 'z' not in col_num.keys():
        col_num['z'] = len(col_num)
        dim = 2
    else:
        dim = 3
    print(' * {}D data provided'.format(dim))

    # initialize the database
    db_path = os.path.splitext(out_path)[0] + '.db'
    conn, cur = init_db(db_path, col_num)

    t_start = time.clock()

    # iterate through the files
    for path in file_list:
        print(' >> {}'.format(path))

        i = find_layer_num(path, regex)
        z = interval * i

        n_invalid = 0
        for row in load_csv(path):
            if not is_valid(col_num, row):
                n_invalid += 1
                continue
            row = patch_z(row, dim, z)
            row = shear(col_num, row, dim, z, angle)
            cur.execute('INSERT INTO tmp.{} VALUES ({})'.format(TABLE_NAME, ','.join(row)))
        print(' .. {} invalid entries'.format(n_invalid))

        # commit the inserted entries
        conn.commit()
        # merge the table
        cur.execute('INSERT INTO main.{0} SELECT * FROM tmp.{0}'.format(TABLE_NAME));
        cur.execute('DELETE FROM tmp.{}'.format(TABLE_NAME))
        conn.commit()

    # drop the in-memory contents
    cur.execute('DROP TABLE IF EXISTS tmp.{}'.format(TABLE_NAME))

    print(' * exporting to \'{}\''.format(out_path))
    # export the combined result
    cur.execute('SELECT * FROM main.{}'.format(TABLE_NAME))
    with open(out_path, 'w') as f:
        writer = csv.writer(f, quoting = csv.QUOTE_NONNUMERIC)
        # write the header (with unit)
        writer.writerow([i[0] + ' ' + HEADER_LUT[i[0]][0] for i in cur.description])
        # write the contents
        writer.writerows(cur)

    t_end = time.clock()

    t_elapsed = t_end - t_start;
    print(' * {0:.3f} seconds elapsed'.format(t_elapsed))

def parse_args():
    parser = argparse.ArgumentParser(description='CSV post processing routines.')
    parser.add_argument('--regex', nargs=1,
                        type=str, default=[DEFAULT_REGEX],
                        help='regex that describes layer numbering schema, default is \'' + DEFAULT_REGEX + '\'')
    parser.add_argument('--angle', metavar='DEG', nargs=1,
                        type=float, default=[0.0],
                        help='shearing angle, perform shearing if supplied')
    parser.add_argument('interval', metavar='INTERVAL', nargs=1,
                        type=float,
                        help='distance (nm) between layers')
    parser.add_argument('src_dir', metavar='FOLDER', nargs=1,
                        type=str,
                        help='folder that contains the CSV files')
    parser.add_argument('-o', '--output', metavar='PATH', nargs=1,
                        type=str, default=[DEFAULT_OUTPUT],
                        help='file path of the merged result, default is \'' + DEFAULT_OUTPUT + '\'')
    return parser.parse_args()

if __name__ == '__main__':
    # parse from the command line
    args = parse_args()

    main(
        args.regex[0],
        args.angle[0],
        args.interval[0],
        args.src_dir[0],
        args.output[0]
    )

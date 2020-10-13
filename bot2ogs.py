import os
import sys
from argparse import ArgumentParser


parser = ArgumentParser()
parser.add_argument('--apikey', type=str, required=True)
args = parser.parse_args()

GTP2OGS = '/tools/node/bin/node /gtp2ogs-node/gtp2ogs/gtp2ogs.js'
APIKEY = args.apikey
username = 'GoGoBoi'

cmd = f'{GTP2OGS} --apikey {APIKEY} --username {username} --hidden --debug --persist \
    --boardsizes 19 --komis all --maxconnectedgames 8 --maxhandicap 0 \
    --noautohandicap --greeting "heyyyyyyyyyy" \
    --farewell "byeeeee hope to see you again" --noclock --speeds blitz,live \
    -- python3 run_gtp.py'

os.system(cmd)

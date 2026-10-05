"""Retry recovery only after the host operator stops the updater and fixes the fault."""
import argparse
import fcntl
from pathlib import Path
from updater.engine import Engine


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--job',required=True);args=p.parse_args()
    with (Path(args.root)/'service.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        engine=Engine(args.root);row=engine.load(args.job)
        if row['status'] not in {'running','recovery_required'}:raise ValueError('Il job non richiede recupero.')
        if engine.current()['commit'] not in {row['commit'],row.get('previous_commit')}:
            raise ValueError('Versione attiva diversa: eseguire una revisione manuale del recupero.')
        engine.recover(row)
        print('Recupero completato. Riavvia il servizio updater.')

if __name__=='__main__':main()

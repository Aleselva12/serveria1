"""Real Docker release/rollback check on the existing disposable deployment CI."""
from pathlib import Path
import tempfile
from updater.engine import Engine
from updater.setup import initialize


def verify(project_root):
    import subprocess
    if __import__('os').environ.get('CORA_DISPOSABLE_DEPLOY_TEST')!='yes':
        raise ValueError('Solo installazione CI sacrificabile.')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=project_root,text=True).strip()
    with tempfile.TemporaryDirectory(prefix='cora-updater-ci-') as temporary:
        root=Path(temporary)/'control'
        initialize(root,project_root,revision)
        engine=Engine(root)
        workspace=engine.create_workspace('CI update')
        file=engine.workspaces/workspace['id']/'files'/'README.md'
        file.write_text(file.read_text()+'\nCI requested update fixture.\n')
        commit=engine.commit_workspace(workspace['id'],'CI requested change')['commit']
        prepare=engine.submit('prepare',workspace['id'],commit)
        engine.execute(engine.load(prepare['id']))
        assert_job(engine, prepare, 'ready')
        apply=engine.submit('apply',commit=commit,release_id=prepare['id'])
        engine.execute(engine.load(apply['id']))
        assert_job(engine, apply, 'completed')
        assert engine.current()['commit']==commit
        rollback=engine.submit('rollback',commit=commit,release_id=prepare['id'])
        engine.execute(engine.load(rollback['id']))
        assert_job(engine, rollback, 'completed')
        assert engine.current()['commit']==revision
        print('REQUESTED UPDATE: BUILD, MIGRATION COPY, APPLY AND FULL ROLLBACK: OK')
        verify_private_backup(engine,Path(temporary))


def verify_private_backup(engine, temporary):
    """Real encrypted backup and isolated PostgreSQL restore, only on disposable CI."""
    import subprocess
    import shutil
    import tarfile
    from uuid import uuid4
    from updater.data_backups import audit,create,unpack
    identity=temporary/'identity.age'
    subprocess.run(['age-keygen','-o',str(identity)],check=True)
    recipient=subprocess.check_output(['age-keygen','-y',str(identity)],text=True).strip()
    expected=(engine.state/'files/proof.txt').read_bytes()
    folder=create(engine,{'destination':str(temporary/'encrypted-backups'),'age_recipient':recipient,
                          'audit_sha256':audit(engine)['audit_sha256'],'keep':2})
    restored=temporary/'decrypted'
    unpack(folder,restored,identity)
    state=temporary/'restored-state';state.mkdir()
    with tarfile.open(restored/'state.tar.gz') as archive:archive.extractall(state,filter='data')
    assert (state/'files/proof.txt').read_bytes()==expected
    # Reuse the updater's disposable DB trial: no import into the active CI database.
    row={'id':str(uuid4()),'kind':'backup-proof','status':'running','phase':'testing','created_at':'ci'}
    destination=engine.path(row['id'])/'backup';destination.mkdir(parents=True)
    shutil.copyfile(restored/'database.dump',destination/'database.dump')
    engine.migration_trial(row,engine.images()['api'])
    row['status']='completed';engine.save(row)
    print('ENCRYPTED BACKUP, DECRYPT, STATE CHECKSUM AND DISPOSABLE DB RESTORE: OK')


def assert_job(engine, job, expected):
    row = engine.load(job['id'])
    if row['status'] != expected:
        # Only disposable CI publishes command output; production APIs keep it private.
        log = engine.root/'last-error.log'
        if log.exists(): print(log.read_text(), flush=True)
    assert row['status'] == expected, engine.public(row)

import sfio

sfio.logger.level = 1


template = sfio.rootdir / 'data'


def test_lmpdump_scanbychunk():
    filename, filetype = 'gold_fcc.dump', 'lmpdump'

    f = sfio.read(template / filename, filetype)
    f.scan(method='line')

    f2 = sfio.init(template / filename, filetype)
    f2.scan(method='chunk')

    assert f.sections == f2.sections


def test_lmpdata_scanbychunk():
    filename, filetype = 'dimer_cis.data', 'lmpdata'

    f = sfio.read(template / filename, filetype)
    f.scan(method='line')

    f2 = sfio.init(template / filename, filetype)
    f2.scan(method='chunk')

    assert f.sections == f2.sections

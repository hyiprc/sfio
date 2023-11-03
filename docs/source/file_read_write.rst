File handling
=============

Reading
-------

.. code-block:: python

    >>> import fio

    # File type is detected by the file extension if not specified
    >>> f = fio.read(fio.rootdir / 'data/gold_fcc.dump', 'lmpdump')

Writing
-------

.. code-block:: python

    # File type is detected by the file extension if not specified
    >>> fio.write('gold_fcc_copy.dump', f, 'lmpdump')

Processing
----------

When a file is read, it automatically scans for byte positions of
frames and sections. The number of frames in a trajectory-type
file can be found using the `len()` function.

.. code-block:: python

    # Displaying the file object
    >>> print(f)  # Output: <Lmpdump File at 0x7f77ad5c9fa0>

    # Finding the number of frames in the file
    >>> print(len(f))  # Output: 4

Frames in a file can be accessed using interger, slice, or fancy
indexing:

.. code-block:: python

    # Access the first or second frame
    >>> print(f[0])  # Output: <Lmpdump Section 'frame', File at 0x7f77ad5c9fa0 seek 0 read 190 bytes>

    # Access the last frame
    >>> print(f[-1])  # Output: <Lmpdump Section 'frame', File at 0x7f4e03f99af0 seek 597 read 193 bytes>

    # Access the first three frames
    >>> print(f[:3])  # Output: [<Lmpdump Section 'frame', File at 0x7f4e03f99af0 seek 0 read 190 bytes>, <Lmpdump Section 'frame', File at 0x7f4e03f99af0 seek 190 read 214 bytes>, <Lmpdump Section 'frame', File at 0x7f4e03f99af0 seek 404 read 193 bytes>]

    # Access the last three frames
    >>> print(f[-3:])  # Output: [<Lmpdump Section 'frame', File at 0x7f4e03f99af0 seek 190 read 214 bytes>, <Lmpdump Section 'frame', File at 0x7f4e03f99af0 seek 404 read 193 bytes>, <Lmpdump Section 'frame', File at 0x7f4e03f99af0 seek 597 read 193 bytes>]

    # Selectively access specific frames
    >>> print(f[[1,5,9]])  # Output: [<Lmpdump Section 'frame', File at 0x7f4e03f99af0 seek 0 read 190 bytes>, <Lmpdump Section 'frame', File at 0x7f4e03f99af0 seek 190 read 214 bytes>, <Lmpdump Section 'frame', File at 0x7f4e03f99af0 seek 597 read 193 bytes>]

Sections in a file can be accessed using the `section()` function. If multiple instances of a section exist, a list of them is returned.

.. code-block:: python

    # Access 'header' section of the second frame
    >>> print(f[1].section('header')  # Output: <Lmpdump Section 'header', File at 0x7f4e03f99af0 seek 190 read 44 bytes>

    # Access all 'header' sections in the file
    >>> print(f.section('header') # Output: [<Lmpdump Section 'header', File at 0x7f4e03f99af0 seek 0 read 41 bytes>, <Lmpdump Section 'header', File at 0x7f4e03f99af0 seek 190 read 44 bytes>, <Lmpdump Section 'header', File at 0x7f4e03f99af0 seek 404 read 44 bytes>, <Lmpdump Section 'header', File at 0x7f4e03f99af0 seek 597 read 44 bytes>]

A frame or section is parsed only when it is casted into various data
types:

.. code-block:: python

    # Simulation box of first frame as `Box` object
    >>> box = f[0].section('box').obj

    >>> print(box)  # Output: <Box object at 0x7f9a74cf4670, {'x0': 0.0, 'y0': 0.0, 'z0': 0.0, 'lx': 4.08, 'ly': 4.08, 'lz': 4.08, 'alpha': 90.0, 'beta': 90.0, 'gamma': 90.0, 'allow_tilt': False, 'bx': 'pp', 'by': 'pp', 'bz': 'pp'}>

    >>> print(box.output)  # Output: mappingproxy({'x0': 0.0, 'y0': 0.0, 'z0': 0.0, 'lx': 4.08, 'ly': 4.08, 'lz': 4.08, 'alpha': 90.0, 'beta': 90.0, 'gamma': 90.0, 'allow_tilt': False, 'bx': 'pp', 'by': 'pp', 'bz': 'pp', 'xlo': 0.0, 'xhi': 4.08, 'ylo': 0.0, 'yhi': 4.08, 'zlo': 0.0, 'zhi': 4.08, 'cos_alpha': 0.0, 'cos_beta': 0.0, 'cos_gamma': 0.0, 'a': 4.08, 'b': 4.08, 'c': 4.08, 'xy': 0.0, 'xz': 0.0, 'yz': 0.0, 'v': array([[4.08, 0.  , 0.  ], [0.  , 4.08, 0.  ], [0.  , 0.  , 4.08]]), 'u': array([[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]), 'u_inv': array([[ 1.,  0.,  0.], [-0.,  1.,  0.], [-0., -0.,  1.]]), 'bn': array([[ 1., -0., -0.], [ 0.,  1., -0.], [ 0.,  0.,  1.]])})

    # First frame as raw text (bytes)
    >>> print(f[0].raw)  # Output: b'ITEM: TIMESTEP\n0\nITEM: NUMBER OF ATOMS\n4\nITEM: BOX BOUNDS pp pp pp\n0.0 4.08\n0.0 4.08\n0.0 4.08\nITEM: ATOMS id type x y z\n1 1 0.0 0.0 0.0\n2 1 2.04 2.04 0.0\n3 1 0.0 2.04 2.04\n4 1 2.04 0.0 2.04\n'

    # First frame as text (str)
    >>> print(f[0].text)
    ITEM: TIMESTEP
    0
    ITEM: NUMBER OF ATOMS
    4
    ITEM: BOX BOUNDS pp pp pp
    0.0 4.08
    0.0 4.08
    0.0 4.08
    ITEM: ATOMS id type x y z
    1 1 0.0 0.0 0.0
    2 1 2.04 2.04 0.0
    3 1 0.0 2.04 2.04
    4 1 2.04 0.0 2.04

    # First frame as file object
    >>> print(f[0].f)  # Output: <_io.BytesIO object at 0x7f4de7da3270>

    # First frame as dict
    >>> print(f[0].dict)  # Output: {'timestep': 0, 'num_atoms': 4, 'box': {'x0': 0.0, 'y0': 0.0, 'z0': 0.0, 'lx': 4.08, 'ly': 4.08, 'lz': 4.08, 'alpha': 90.0, 'beta': 90.0, 'gamma': 90.0, 'allow_tilt': False, 'bx': 'pp', 'by': 'pp', 'bz': 'pp'}, 'atoms': {'type': array([1, 1, 1]), 'x': array([2.04, 0.  , 2.04]), 'y': array([2.04, 2.04, 0.  ]), 'z': array([0.  , 2.04, 2.04])}}

    # First frame as DataFrame
    >>> print(f[0].df)
       type     x     y     z
    0     1  2.04  2.04  0.00
    1     1  0.00  2.04  2.04
    2     1  2.04  0.00  2.04

    # Associated attributes of the DataFrame
    >>> print(f[0].df.attrs)  # Output: {'timestep': 0, 'num_atoms': 4, 'box': {'x0': 0.0, 'y0': 0.0, 'z0': 0.0, 'lx': 4.08, 'ly': 4.08, 'lz': 4.08, 'alpha': 90.0, 'beta': 90.0, 'gamma': 90.0, 'allow_tilt': False, 'bx': 'pp', 'by': 'pp', 'bz': 'pp'}}

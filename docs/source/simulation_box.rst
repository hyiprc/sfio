Simulation box
==============

The ``Box`` module defines and converts between different simulation
`box representations <#supported-box-types>`_.

A simulation ``box`` instance is initialized using the ``sfio.Box``
class.

.. code-block:: python

    >>> import sfio
    >>> box = sfio.Box()

``box`` contains information that can be accessed using dictionary
keys. A subset of keys (*a.k.a.*, `input parameters
<#box-input-parameters>`_) can be assigned to values.

.. code-block:: python

    # 'lx' is an input parameter
    >>> print(box['lx'])
    1.0
    >>> box['lx'] = 100.0
    >>> print(box['lx'])
    100.0
    >>> box['lx'] = 1.0

    # 'a' is not an input parameter
    >>> box['a'] = 2.0
    KeyError: "'a' is not a Box input parameter"


Box input parameters
--------------------

``box`` is defined by 12 independent input parameters:

+-------+------+-------+---------------------+
|       |      |       |                     |
+=======+======+=======+=====================+
| x0    | y0   | z0    | # box origin        |
+-------+------+-------+---------------------+
| lx    | ly   | lz    | # box length        |
+-------+------+-------+---------------------+
| alpha | beta | gamma | # box tilt angle    |
+-------+------+-------+---------------------+
| bx    | by   | bz    | # box boundary type |
+-------+------+-------+---------------------+

A dictionary of all input parameters and their values can be accessed
(and assigned) via the ``box.input`` attribute:

.. code-block:: python

    >>> print(box.input)
    {
      'x0': 0.0, 'y0': 0.0, 'z0': 0.0,
      'lx': 1.0, 'ly': 1.0, 'lz': 1.0,
      'alpha': 90.0, 'beta': 90.0, 'gamma': 90.0, 'allow_tilt': False,
      'bx': 'pp', 'by': 'pp', 'bz': 'pp',
    }

``alpha`` is the angle between basis vectors ``b`` and ``c``,
``beta`` is the angle between basis vectors ``a`` and ``c``,
``gamma`` is the angle between basis vectors ``a`` and ``b``.

Note that the ``allow_tilt`` key can be set to ``True`` (triclinic
box) or ``False`` (otrhogonal box), but it is partially dependent on
the box tilt angles, *i.e.*, it becomes ``True`` if ``alpha``,
``beta``, or ``gamma`` is not 90°.

Box boundary types is indicated by one or two letters, for the lower
and upper boundaries, as defined in `LAMMPS
<https://docs.lammps.org/boundary.html>`_. The letters can be p
(periodic), f (fixed), s (shrink-wrap), or m (shrink-wrap with a
minimum).


Box output parameters
---------------------

From the input parameters, ``box`` calculates other parameters
associated with the different `box representations
<#supported-box-types>`_. A read-only dictionary of all
input and derived parameters and their values can be accessed via
the ``box.output`` attribute:

.. code-block:: python

    >>> print(box.output)
    {
      'x0': 0.0, 'y0': 0.0, 'z0': 0.0,
      'lx': 1.0, 'ly': 1.0, 'lz': 1.0,
      'alpha': 90.0, 'beta': 90.0, 'gamma': 90.0, 'allow_tilt': False,
      'bx': 'pp', 'by': 'pp', 'bz': 'pp',
      'xlo': 0.0, 'xhi': 1.0, 'ylo': 0.0, 'yhi': 1.0, 'zlo': 0.0, 'zhi': 1.0,
      'cos_alpha': 0.0, 'cos_beta': 0.0, 'cos_gamma': 0.0,
      'a': 1.0, 'b': 1.0, 'c': 1.0, 'xy': 0.0, 'xz': 0.0, 'yz': 0.0,
      'v': array([[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]),
      'u': array([[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]),
      'u_inv': array([[ 1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]),
      'bn': array([[ 1., 0., 0.], [ 0., 1., 0.], [ 0., 0., 1.]]),
    }

The derived parameters are calculated from the following equations:

.. code-block::

    xlo = x0
    ylo = y0
    zlo = z0

    xhi = x0 + lx
    yhi = y0 + ly
    zhi = z0 + lz

    cos_alpha = cos(alpha)
    cos_beta = cos(beta)
    cos_gamma = cos(gamma)

    a = lx
    b = ly / sqrt(1 - cos_gamma^2)
    c = lz / sqrt(1 - cos_beta^2 - (cos_alpha - cos_gamma ⋅ cos_beta)^2 / (1 - cos_gamma^2))

    xy = b ⋅ cos_gamma
    xz = c ⋅ cos_beta
    yz = (b ⋅ c ⋅ cos_alpha - xy ⋅ xz) / ly

    v = array([[lx, 0.0, 0.0], [xy, ly, 0.0], [xz, yz, lz]])


Supported box types
-------------------

**Basis Vectors** ('basis', 'poscar'):

+--------+--------+--------+
|        |        |        |
+========+========+========+
| v_a[0] | v_a[1] | v_a[2] |
+--------+--------+--------+
| v_b[0] | v_b[1] | v_b[2] |
+--------+--------+--------+
| v_c[0] | v_c[1] | v_c[2] |
+--------+--------+--------+

**Lattice Parameters** ('lattice', 'vmd'):

a, b, c, alpha, beta, gamma

**LAMMPS** ('lmpdata', 'lmpdump'):

xlo, ylo, zlo, xhi, yhi, zhi, xy, xz, yz  # data file

xlo, xhi, xy, ylo, yhi, xz, zlo, zhi, yz  # dump file

**Others** ('dcd'):

a, cos_gamma, b, cos_beta, cos_alpha, c  # DCD file


Box input parameters from specific box type
-------------------------------------------

The ``box.set_input()`` method converts the supported box types to the
box input parameters. If the keyword argument ``typ`` is not
specificed, the method will guess the box type based on the input
argument.

.. code-block:: python

    # 'lattice' box type ("a b c alpha beta gamma") requires 6 numbers
    >>> box.set_input('120 150 130 90 90 90', typ='lattice')
    >>> print(box)

    # ----- input parameters (origin, bb-length, angle, boundary) -----
    {'x0': 0.0, 'y0': 0.0, 'z0': 0.0, 'lx': 120.0, 'ly': 150.0, 'lz': 130.0, 'alpha': 90.0, 'beta': 90.0, 'gamma': 90.0, 'allow_tilt': False, 'bx': 'pp', 'by': 'pp', 'bz': 'pp'}

    # ----- basis Vectors -----
       120.000000000      0.000000000      0.000000000
         0.000000000    150.000000000      0.000000000
         0.000000000      0.000000000    130.000000000

    # ----- lattice Parameters -----
    120 150 130 90 90 90  a b c alpha beta gamma
    # alpha is between b c, beta a c, gamma a b

    # ----- lammps data file -----
     0.0000000 120.0000000  xlo xhi
     0.0000000 150.0000000  ylo yhi
     0.0000000 130.0000000  zlo zhi
     0.0000000 0.0000000 0.0000000  xy xz yz

    # ----- lammps dump file -----
    ITEM: BOX BOUNDS xy xz yz pp pp pp
    0.0000000 120.0000000 0.0000000  xlo xhi xy
    0.0000000 150.0000000 0.0000000  ylo yhi xz
    0.0000000 130.0000000 0.0000000  zlo zhi yz

    # ----- dcd file ----
    120 0 150 0 0 130  a cos_gamma b cos_beta cos_alpha c

Command line
------------

.. code-block:: console

    $ python -m sfio.box [input_values]

Other box functions
-------------------

``box.fractional_xyz()``

``box.bbcheck()``

``box.extend()``

``box.wrap()``

``box.ghost()``

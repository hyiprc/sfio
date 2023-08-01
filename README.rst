FIO: File I/O
=============

The `fio` module is a Python library for efficient file input/output operations. It handles various file formats commonly used in computational materials science research.

Key Features
------------

+ Supports triclinic (non-orthogonal) simulation boxes and the conversion between basis vectors, lattice parameters, and LAMMPS box representations.

+ Slicing/indexing mechanism for multi-frames (trajectory) file types.

Installation
------------

.. code-block:: console

    $ which python  # confirm the location
    $ python -m pip install -e .[dev]
    $ pre-commit install

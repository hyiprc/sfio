FIO: File I/O
=============

The `sfio` module is a Python library for efficient file input/output operations. It handles various file formats commonly used in computational materials science research.

Key Features
------------

+ **Simulation Box Conversions:** Supports triclinic (non-orthogonal) simulation boxes. Converts between basis vectors, lattice parameters, and LAMMPS box representations. <https://github.com/hyiprc/sfio/blob/main/docs/source/simulation_box.rst>

+ **File Parsing and Data Type Casting:** Provides a Slicing/indexing mechanism for multi-frames (trajectory) file types. Parsing sections in a file and cast them into different data types. <https://github.com/hyiprc/sfio/blob/main/docs/source/file_read_write.rst>

+ **JSON/YAML data serialization:** Encode/decode numpy.ndarray and selected Python objects to/from data URLs.


Quick installation
------------------

.. code-block:: console

    python -m pip install git+https://github.com/hyiprc/sfio.git

To update or reinstall,

.. code-block:: console

    python -m pip install --force-reinstall --no-deps git+https://github.com/hyiprc/sfio.git


Developer installation
----------------------

.. code-block:: console

    $ which python  # confirm the location
    $ git clone https://github.com/hyiprc/sfio.git
    $ cd sfio
    $ python -m pip install -e .[dev]
    $ pre-commit install

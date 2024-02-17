FIO: File I/O
=============

The `fio` module is a Python library for efficient file input/output operations. It handles various file formats commonly used in computational materials science research.

Key Features
------------

+ **Simulation Box Conversions:** Supports triclinic (non-orthogonal) simulation boxes. Converts between basis vectors, lattice parameters, and LAMMPS box representations. <https://github.com/hyiprc/fio/blob/main/docs/source/simulation_box.rst>

+ **File Parsing and Data Type Casting:** Provides a Slicing/indexing mechanism for multi-frames (trajectory) file types. Parsing sections in a file and cast them into different data types. <https://github.com/hyiprc/fio/blob/main/docs/source/file_read_write.rst>


Quick installation
------------------

.. code-block:: console

    $ python -m pip install git+https://github.com/hyiprc/fio.git

To update or reinstall,

.. code-block:: console

    $ python -m pip install --force-reinstall --no-deps git+https://github.com/hyiprc/fio.git


Dev installation
----------------

.. code-block:: console

    $ which python  # confirm the location
    $ git clone https://github.com/hyiprc/fio.git
    $ cd fio
    $ python -m pip install -e .[dev]
    $ pre-commit install

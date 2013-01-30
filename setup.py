
"""
Socraticqs
==========

Socraticqs is an open-source In-Class Question System designed
for teaching by asking questions that
students answer in-class using their laptops or smartphones.
Concretely:

* it is a lightweight web server written in Python
  (usually run on the instructor's laptop)
  that students point their web browsers at, giving them an
  easy interface for answering the questions you assign.
* it also gives the instructor an easy web interface for
  walking the students through questions one step at a time.
* it captures all student responses in a database (sqlite3)
  for generating reports and whatever data analysis you want.
"""

import warnings

try:
    from setuptools import setup
    # setuptools can automatically install dependencies for you
    install_requires = ['CherryPy']
    has_setuptools = True
except ImportError:
    warnings.warn('Setuptools not found, falling back to distutils')
    from distutils.core import setup
    has_setuptools = False

CLASSIFIERS = """
Development Status :: 3 - Alpha
Operating System :: MacOS :: MacOS X
Operating System :: Microsoft :: Windows :: Windows NT/2000
Operating System :: OS Independent
Operating System :: POSIX
Operating System :: POSIX :: Linux
Operating System :: Unix
Programming Language :: Python
Intended Audience :: Education
Topic :: Education
Topic :: Education :: Computer Aided Instruction (CAI)
"""

# split into lines and filter empty ones
CLASSIFIERS = filter(None, CLASSIFIERS.splitlines())

entry_points = {
    'console_scripts': [
        'socraticqs_init = socraticqs.coursedb:main',
        'socraticqs = socraticqs.web:main',
        ],
    }

def try_install(**kwargs):
    'try to install socraticqs using setup()'
    setup(
        name = 'socraticqs',
        version= '0.3',
        description = 'Socraticqs is an open-source In-Class Question System for teaching by asking questions (which students answer in-class using their laptops or smartphones).',
        long_description = __doc__,
        author = "Christopher Lee",
        author_email='leec@chem.ucla.edu',
        url = 'https://github.com/cjlee112/socraticqs',
        license = 'New BSD License',
        classifiers = CLASSIFIERS,

        packages = ['socraticqs'],
        **kwargs
     )

def main():
    if has_setuptools:
        try_install(install_requires=install_requires,
                    entry_points=entry_points)
    else:
        try_install()
        warnings.warn('''Because setuptools is missing, unable to install
        socraticqs and socraticqs_init command entry points.  It will
        probably be easier to just run socraticqs commands directly
        via the source code directory (here).  See the docs for details.''')

if __name__ == '__main__':
    main()

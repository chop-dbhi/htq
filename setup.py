import sys
from setuptools import setup, find_packages

if sys.version_info < (3, 3, 0):
    raise EnvironmentError('Python version not supported')


kwargs = {
    'name': 'htq',

    'version': __import__('htq').get_version(),

    'description': 'HTTP Task Queue',

    'url': 'https://github.com/cbmi/htq/',

    'author': 'Byron Ruth',

    'author_email': 'b@devel.io',

    'license': 'BSD',

    'keywords': 'http task queue',

    'classifiers': [
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: BSD License',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],

    'packages': find_packages(exclude=['tests']),

    'install_requires': [
        'requests>=2.4.1,<2.5',
        'redis>=2.10.3,<2.11',
        'hiredis>=0.1.4,<0.2',
        'docopt>=0.6.2,<0.7',
        'flask>=0.10.1,<0.11',
    ],

    'scripts': ['bin/htq'],
}

setup(**kwargs)

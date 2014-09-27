#!/usr/bin/env python

if __name__ == '__main__':
    import sys
    import unittest

    loader = unittest.TestLoader()
    runner = unittest.runner.TextTestRunner()

    args = sys.argv[1:]
    tests = None

    if args:
        if 'TestCase' in args[0]:
            tests = loader.loadTestsFromNames(args)
        else:
            start_dir = args[0]
    else:
        start_dir = 'tests'

    if tests is None:
        tests = loader.discover(start_dir, 'test_*.py', top_level_dir='tests')

    result = runner.run(tests)

    if result.errors or result.failures:
        sys.exit(1)

# -*- coding: utf-8; mode: python; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- vim:fenc=utf-8:ft=python:et:sw=4:ts=4:sts=4
# Copyright (c) 2003-2013 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
"""Emacs and Flymake compatible Pylint.

This script is for integration with emacs and is compatible with flymake mode.

epylint walks out of python packages before invoking pylint. This avoids
reporting import errors that occur when a module within a package uses the
absolute import path to get another module within this package.

For example:
    - Suppose a package is structured as

        a/__init__.py
        a/b/x.py
        a/c/y.py

   - Then if y.py imports x as "from a.b import x" the following produces pylint
     errors

       cd a/c; pylint y.py

   - The following obviously doesn't

       pylint a/c/y.py

   - As this script will be invoked by emacs within the directory of the file
     we are checking we need to go out of it to avoid these false positives.


You may also use py_run to run pylint with desired options and get back (or not)
its output.
"""

import sys, os, re
from subprocess import Popen, PIPE


def lint(filename, options=None):
    """Pylint the given file.

    When run from emacs we will be in the directory of a file, and passed its
    filename.  If this file is part of a package and is trying to import other
    modules from within its own package or another package rooted in a directory
    below it, pylint will classify it as a failed import.

    To get around this, we traverse down the directory tree to find the root of
    the package this module is in.  We then invoke pylint from this directory.

    Finally, we must correct the filenames in the output generated by pylint so
    Emacs doesn't become confused (it will expect just the original filename,
    while pylint may extend it with extra directories if we've traversed down
    the tree)
    """
    # traverse downwards until we are out of a python package
    fullPath = os.path.abspath(filename)
    parentPath, childPath = os.path.dirname(fullPath), os.path.basename(fullPath)

    while parentPath != "/" and os.path.exists(os.path.join(parentPath, '__init__.py')):
        childPath = os.path.join(os.path.basename(parentPath), childPath)
        parentPath = os.path.dirname(parentPath)

    # Start pylint
    # Ensure we use the python and pylint associated with the running epylint
    lintPath = os.path.join(os.path.dirname(__file__), 'lint.py')
    options = options or ['--disable=C,R,I']
    cmd = [sys.executable, lintPath] + options + ['--msg-template',
            '{path}:{line}: [{symbol}, {obj}] {msg}', '-r', 'n', childPath]
    process = Popen(cmd, stdout=PIPE, cwd=parentPath, universal_newlines=True)

    # The parseable line format is '%(path)s:%(line)s: [%(sigle)s%(obj)s] %(msg)s'
    # NOTE: This would be cleaner if we added an Emacs reporter to pylint.reporters.text ..
    regex = re.compile(r"\[(?P<type>[WE])(?P<remainder>.*?)\]")

    def _replacement(mObj):
        "Alter to include 'Error' or 'Warning'"
        if mObj.group("type") == "W":
            replacement = "Warning"
        else:
            replacement = "Error"
        # replace as "Warning (W0511, funcName): Warning Text"
        return "%s (%s%s):" % (replacement, mObj.group("type"), mObj.group("remainder"))

    for line in process.stdout:
        # remove pylintrc warning
        if line.startswith("No config file found"):
            continue
        line = regex.sub(_replacement, line, 1)
        # modify the file name thats output to reverse the path traversal we made
        parts = line.split(":")
        if parts and parts[0] == childPath:
            line = ":".join([filename] + parts[1:])
        print line,

    process.wait()
    return process.returncode


def py_run(command_options='', return_std=False, stdout=None, stderr=None,
           script='epylint'):
    """Run pylint from python

    ``command_options`` is a string containing ``pylint`` command line options;
    ``return_std`` (boolean) indicates return of created standart output
    and error (see below);
    ``stdout`` and ``stderr`` are 'file-like' objects in which standart output
    could be written.

    Calling agent is responsible for stdout/err management (creation, close).
    Default standart output and error are those from sys,
    or standalone ones (``subprocess.PIPE``) are used
    if they are not set and ``return_std``.

    If ``return_std`` is set to ``True``, this function returns a 2-uple
    containing standart output and error related to created process,
    as follows: ``(stdout, stderr)``.

    A trivial usage could be as follows:
        >>> py_run( '--version')
        No config file found, using default configuration
        pylint 0.18.1,
            ...

    To silently run Pylint on a module, and get its standart output and error:
        >>> (pylint_stdout, pylint_stderr) = py_run( 'module_name.py', True)
    """
    # Create command line to call pylint
    if os.name == 'nt':
        script += '.bat'
    command_line = script + ' ' + command_options
    # Providing standart output and/or error if not set
    if stdout is None:
        if return_std:
            stdout = PIPE
        else:
            stdout = sys.stdout
    if stderr is None:
        if return_std:
            stderr = PIPE
        else:
            stderr = sys.stderr
    # Call pylint in a subprocess
    p = Popen(command_line, shell=True, stdout=stdout, stderr=stderr,
              universal_newlines=True)
    p.wait()
    # Return standart output and error
    if return_std:
        return (p.stdout, p.stderr)


def Run():
    if len(sys.argv) == 1:
        print "Usage: %s <filename> [options]" % sys.argv[0]
        sys.exit(1)
    elif not os.path.exists(sys.argv[1]):
        print "%s does not exist" % sys.argv[1]
        sys.exit(1)
    else:
        sys.exit(lint(sys.argv[1], sys.argv[1:]))


if __name__ == '__main__':
    Run()


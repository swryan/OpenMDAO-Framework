"""
Write Python egg files, either directly or via :mod:`setuptools`.
Supports what's needed for saving and loading components/simulations.

Both :func:`write` and :func:`write_via_setuptools` have the following
arguments:

name : string
    Must be an alphanumeric string.

version : string
    Must be an alphanumeric string.

doc : string
    Used for the `Summary` and `Description` entries in the egg's metadata.

entry_map : dict
    A :mod:`pkg_resources` :class:`EntryPoint` map: a dictionary mapping group
    names to dictionaries mapping entry point names to :class:`EntryPoint`
    objects.

src_files : list
    List of non-Python files to include.

distributions : list
    List of Distributions this egg depends on.  It is used for the `Requires`
    entry in the egg's metadata.

modules : list
    List of module names not found in a distribution that this egg depends on.
    It is used for the `Requires` entry in the egg's metadata and is also
    recorded in the 'openmdao_orphans.txt' resource.

dst_dir : string
    The directory to write the egg to.

logger : Logger
    Used for recording progress, etc.

observer : callable
    Will be called via an :class:`EggObserver` intermediary.
"""

import copy
import os.path
import pkg_resources
import re
import subprocess
import sys
import time
import zipfile

from openmdao.util import eggobserver
from openmdao.util.testutil import find_python

__all__ = ('egg_filename', 'write', 'write_via_setuptools')

# Legal egg strings.
_EGG_NAME_RE = re.compile('[a-zA-Z][_a-zA-Z0-9]*')
_EGG_VERSION_RE = \
    re.compile('([a-zA-Z0-9][_a-zA-Z0-9]*)+(\.[_a-zA-Z0-9][_a-zA-Z0-9]*)*')


def egg_filename(name, version):
    """
    Returns name for egg file as generated by :mod:`setuptools`.

    name : string
        Must be alphanumeric.

    version : string
        Must be alphanumeric.
    """
    assert name and isinstance(name, basestring)
    match = _EGG_NAME_RE.search(name)
    if match is None or match.group() != name:
        raise ValueError('Egg name must be alphanumeric')

    assert version and isinstance(version, basestring)
    match = _EGG_VERSION_RE.search(version)
    if match is None or match.group() != version:
        raise ValueError('Egg version must be alphanumeric')

    name = pkg_resources.to_filename(pkg_resources.safe_name(name))
    version = pkg_resources.to_filename(pkg_resources.safe_version(version))
    return '%s-%s-py%s.egg' % (name, version, sys.version[:3])


def write(name, version, doc, entry_map, src_files, distributions, modules,
          dst_dir, logger, observer=None, compress=True):
    """
    Write egg in the manner of :mod:`setuptools`, with some differences:

    - Writes directly to the zip file, avoiding some intermediate copies.
    - Doesn't compile any Python modules.

    Returns the egg's filename.
    """
    observer = eggobserver.EggObserver(observer, logger)

    egg_name = egg_filename(name, version)
    egg_path = os.path.join(dst_dir, egg_name)

    distributions = sorted(distributions, key=lambda dist: dist.project_name)
    modules = sorted(modules)

    sources = []
    files = []
    size = 0 # Approximate (uncompressed) size. Used to set allowZip64 flag.

    # Collect src_files.
    for path in src_files:
        path = os.path.join(name, path)
        files.append(path)
        size += os.path.getsize(path)

    # Collect Python modules.
    for dirpath, dirnames, filenames in os.walk('.', followlinks=True):
        dirs = copy.copy(dirnames)
        for path in dirs:
            if not os.path.exists(os.path.join(dirpath, path, '__init__.py')):
                dirnames.remove(path)
        for path in filenames:
            if path.endswith('.py'):
                path = os.path.join(dirpath[2:], path)  # Skip leading './'
                files.append(path)
                size += os.path.getsize(path)
                sources.append(path)

    # Package info -> EGG-INFO/PKG-INFO
    pkg_info = []
    pkg_info.append('Metadata-Version: 1.1')
    pkg_info.append('Name: %s' % pkg_resources.safe_name(name))
    pkg_info.append('Version: %s' % pkg_resources.safe_version(version))
    pkg_info.append('Summary: %s' % doc.strip().split('\n')[0])
    pkg_info.append('Description: %s' % doc.strip())
    pkg_info.append('Author-email: UNKNOWN')
    pkg_info.append('License: UNKNOWN')
    pkg_info.append('Platform: UNKNOWN')
    for dist in distributions:
        pkg_info.append('Requires: %s (%s)' % (dist.project_name, dist.version))
    for module in modules:
        pkg_info.append('Requires: %s' % module)
    pkg_info = '\n'.join(pkg_info)+'\n'
    sources.append(name+'.egg-info/PKG-INFO')
    size += len(pkg_info)

    # Dependency links -> EGG-INFO/dependency_links.txt
    dependency_links = '\n'
    sources.append(name+'.egg-info/dependency_links.txt')
    size += len(dependency_links)

    # Entry points -> EGG-INFO/entry_points.txt
    entry_points = []
    for entry_group in sorted(entry_map.keys()):
        entry_points.append('[%s]' % entry_group)
        for entry_name in sorted(entry_map[entry_group].keys()):
            entry_points.append('%s' % entry_map[entry_group][entry_name])
        entry_points.append('')
    entry_points = '\n'.join(entry_points)+'\n'
    sources.append(name+'.egg-info/entry_points.txt')
    size += len(entry_points)

    # Unsafe -> EGG-INFO/not-zip-safe
    not_zip_safe = '\n'
    sources.append(name+'.egg-info/not-zip-safe')
    size += len(not_zip_safe)

    # Requirements -> EGG-INFO/requires.txt
    requirements = [str(dist.as_requirement()) for dist in distributions]
    requirements = '\n'.join(requirements)+'\n'
    sources.append(name+'.egg-info/requires.txt')
    size += len(requirements)

    # Modules not part of a distribution -> EGG-INFO/openmdao_orphans.txt
    orphans = '\n'.join(modules)+'\n'
    sources.append(name+'.egg-info/openmdao_orphans.txt')
    size += len(orphans)

    # Top-level names -> EGG-INFO/top_level.txt
    top_level = '%s\n' % name
    sources.append(name+'.egg-info/top_level.txt')
    size += len(top_level)

    # Manifest -> EGG-INFO/SOURCES.txt
    sources.append(name+'.egg-info/SOURCES.txt')
    sources = '\n'.join(sorted(sources))+'\n'
    size += len(sources)

    # Open zipfile.
    logger.debug('Creating %s', egg_path)
    zip64 = size > zipfile.ZIP64_LIMIT
    compression = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    egg = zipfile.ZipFile(egg_path, 'w', compression, zip64)

    stats = {'completed_files': 0., 'total_files': float(8+len(files)),
             'completed_bytes': 0., 'total_bytes': float(size)}

    # Write egg info.
    _write_info(egg, 'PKG-INFO', pkg_info, observer, stats)
    _write_info(egg, 'dependency_links.txt', dependency_links, observer, stats)
    _write_info(egg, 'entry_points.txt', entry_points, observer, stats)
    _write_info(egg, 'not-zip-safe', not_zip_safe, observer, stats)
    _write_info(egg, 'requires.txt', requirements, observer, stats)
    _write_info(egg, 'openmdao_orphans.txt', orphans, observer, stats)
    _write_info(egg, 'top_level.txt', top_level, observer, stats)
    _write_info(egg, 'SOURCES.txt', sources, observer, stats)

    # Write collected files.
    for path in sorted(files):
        _write_file(egg, path, observer, stats)

    observer.complete(egg_name)

    egg.close()
    if os.path.getsize(egg_path) > zipfile.ZIP64_LIMIT:
        logger.warning('Egg zipfile requires Zip64 support to unzip.')
    return egg_name

def _write_info(egg, name, info, observer, stats):
    """ Write info string to egg. """
    path = os.path.join('EGG-INFO', name)
    observer.add(path, stats['completed_files'] / stats['total_files'],
                       stats['completed_bytes'] / stats['total_bytes'])
    egg.writestr(path, info)
    stats['completed_files'] += 1
    stats['completed_bytes'] += len(info)

def _write_file(egg, path, observer, stats):
    """ Write file to egg. """
    observer.add(path, stats['completed_files'] / stats['total_files'],
                       stats['completed_bytes'] / stats['total_bytes'])
    egg.write(path)
    stats['completed_files'] += 1
    stats['completed_bytes'] += os.path.getsize(path)


def write_via_setuptools(name, version, doc, entry_map, src_files,
                         distributions, modules, dst_dir, logger, observer):
    """ Write an egg via :mod:`setuptools`. Returns the egg's filename. """ 
    observer = eggobserver.EggObserver(observer, logger)
    egg_name = egg_filename(name, version)

    _write_setup_py(name, version, doc, entry_map, src_files, distributions,
                    modules, observer)

    # TODO: parse process output and relay to observer.
    observer.add('write-via-setuptools', 0, 0)

    # Find OpenMDAO python command.
    python = find_python()

    # Use environment since 'python' might not recognize '-u'.
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    logger.debug('using %s', python)
    proc = subprocess.Popen([python, 'setup.py', 'bdist_egg', '-d', dst_dir],
                            env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    output = []
    while proc.returncode is None:
        line = proc.stdout.readline()
        if line:
            line = line.rstrip()
            logger.debug('    '+line)
            output.append(line)
        time.sleep(0.1)
        proc.poll()
    line = proc.stdout.readline()
    while line:
        line = line.rstrip()
        logger.debug('    '+line)
        output.append(line)
        line = proc.stdout.readline()

    if proc.returncode != 0:
        for line in output:
            logger.error('    '+line)
        msg = 'save_to_egg failed due to setup.py error %d' % proc.returncode
        observer.exception(msg)
        raise RuntimeError(msg)

    observer.complete(egg_name)

    return egg_name


def _write_setup_py(name, version, doc, entry_map, src_files, distributions,
                    modules, observer):
    """ Write setup.py file for installation later. """
    out = open('setup.py', 'w')
    out.write('import setuptools\n')

    out.write('\npackage_files = [\n')
    for filename in sorted(src_files):
        path = os.path.join(name, filename)
        if not os.path.exists(path):
            msg = "Can't save, '%s' does not exist" % path
            observer.exception(msg)
            raise ValueError(msg)
        out.write("    '%s',\n" % filename.replace('\\', '/'))
    out.write(']\n')
    
    out.write('\nrequirements = [\n')
    for dist in sorted(distributions, key=lambda dist: dist.project_name):
        out.write("    '%s',\n" % dist.as_requirement())
    out.write(']\n')
    
    # Required modules not found in a distribution.
    out.write('\nopenmdao_orphans = [\n')
    for module in sorted(modules):
        out.write("    '%s',\n" % module)
    out.write(']\n')

    out.write("\nentry_points = {\n")
    for entry_group in sorted(entry_map.keys()):
        out.write("    '%s': [\n" % entry_group)
        for entry_name in sorted(entry_map[entry_group].keys()):
            out.write("        '%s',\n" % entry_map[entry_group][entry_name])
        out.write("    ],\n")
    out.write("    'distutils.setup_keywords': [\n")
    out.write("        'openmdao_orphans = setuptools.dist:assert_string_list',\n")
    out.write("    ],\n")
    out.write("    'egg_info.writers': [\n")
    out.write("        'openmdao_orphans.txt = setuptools.command.egg_info:write_arg',\n")
    out.write("    ],\n")
    out.write("}\n")

    if not [entry_point for entry_point in
            pkg_resources.iter_entry_points('distutils.setup_keywords',
                                            'openmdao_orphans')]:
        out.write("""

# Hack to get 'dynamically' added keyword handlers to actually work
# from a blank slate.  Basically, setuptools requires pkg_resources to
# have entry points defined for the entry points we want to define ;-(
# An alternative is to run setup twice, with the result of the first
# run providing pkg_resources with entry points to be used by the second
# run (and ignoring warnings about bad keywords in the first run).

import os.path
import setuptools.dist
import setuptools.command.egg_info

orig_init = setuptools.dist.Distribution.__init__
orig_finalize = setuptools.dist.Distribution.finalize_options
orig_run = setuptools.command.egg_info.egg_info.run

def patched_init(self, attrs=None):
    ''' Add attribute so we are allowed to use the keyword. '''
    setattr(self, 'openmdao_orphans', None)
    orig_init(self, attrs)

def patched_finalize(self):
    ''' Run dynamic keyword handler. '''
    orig_finalize(self)
    name = 'openmdao_orphans'
    value = getattr(self, name, None)
    if value is not None:
        setuptools.dist.assert_string_list(self, name, value)

def patched_run(self):
    ''' Run dynamic keyword writer. '''
    orig_run(self)
    name = 'openmdao_orphans.txt'
    setuptools.command.egg_info.write_arg(self, name,
                                          os.path.join(self.egg_info, name))
    self.find_sources()

setuptools.dist.Distribution.__init__ = patched_init
setuptools.dist.Distribution.finalize_options = patched_finalize
setuptools.command.egg_info.egg_info.run = patched_run

""")

    out.write("""
setuptools.setup(
    name='%(name)s',
    version='%(version)s',
    description='%(summary)s',
    long_description='''%(desc)s''',
    packages=setuptools.find_packages(),
    package_data={'%(name)s': package_files},
    zip_safe=False,
    install_requires=requirements,
    entry_points=entry_points,
    openmdao_orphans=openmdao_orphans,
)
""" % {'name': name,
       'version': version,
       'summary': doc.strip().split('\n')[0],
       'desc': doc.strip()})

    out.close()


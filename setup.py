from setuptools import setup, find_packages


__version__ = '0.0.4'

with open("README.md", "r") as fh:
    long_desc = fh.read()


setup(
    name='cilantro_ee',
    version=__version__,
    packages=find_packages(exclude=['docs', 'ops', 'docker', 'deprecated']),

    # Note install requirements have to be same as dev-requirement.txt (for aws)
    install_requires=[
        # utils
        'coloredlogs',
        'checksumdir==1.1.7',
        'PyNaCl==1.2.1',
        'pyzmq==19.0.0',
        'requests>=2.21.0',
        'uvloop>=0.9.1',
        'aiohttp',
        'sanic==19.6.3',
        'sanic-limiter>=0.1.3',
        'Sanic-Cors>=0.9.9.post1',
        'contracting',
        'pymongo',
        'termcolor',
        'Cython==0.29',
        'argparse_actions==0.4.4',
        'psutil==5.7.0',
        'python-crontab'
    ],
    entry_points={
        'console_scripts': [
            'cil=cilantro_ee.cli.cmd:main'
        ],
    },
    zip_safe=False,
    package_data={
        '': [],
        'cilantro_ee': ['cilantro_ee.conf'],
    },
    description="Lamden Blockchain",
    long_description= long_desc,
    long_description_content_type="text/markdown",
    url='https://github.com/Lamden/cilantro-enterprise',
    author='Lamden',
    author_email='team@lamden.io',
    classifiers=[
        'Programming Language :: Python :: 3.6',
    ],
    python_requires='>=3.6.5',
)

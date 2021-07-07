from setuptools import setup, find_packages

VERSION = '0.0.1'
DESCRIPTION = 'Nikon RFA'
LONG_DESCRIPTION = 'Nikon Remote Focus Assistant'

# Setting up
setup(
    # the name must match the folder name 'verysimplemodule'
    name="nikonrfa",
    version=VERSION,
    author="",
    author_email="<@email.com>",
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    packages=find_packages(),
    install_requires=['pyserial'],  # add any additional packages that
    # needs to be installed along with your package. Eg: 'caer'

    keywords=['python', 'NikonRFA'],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Education",
        "Programming Language :: Python :: 3",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
    ]
)
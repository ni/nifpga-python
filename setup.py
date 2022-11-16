from setuptools import setup, find_packages
import os

# The VERSION file is codegned by the build.
# setup.py needs to be in version control, but checking versions into that is problematic
def get_version():
    version = None
    script_dir = os.path.dirname(os.path.realpath(__file__))
    script_dir = os.path.join(script_dir, "nifpga")
    if not os.path.exists(os.path.join(script_dir, "VERSION")):
        version = "1.0.0.dev0"
    else:
        with open(os.path.join(script_dir, "VERSION"), "r") as version_file:
            version = version_file.read().rstrip()
    return version


def get_long_description():
    this_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists("README.md"):
        return ""
    else:
        with open(os.path.join(this_dir, "README.md")) as readme:
            return readme.read().strip()


setup(name="nifpga",
      description="Python API for interacting with National Instrument's LabVIEW FPGA Devices",
      long_description=get_long_description(),
      long_description_content_type="text/markdown",
      version=get_version(),
      packages=find_packages(),
      install_requires=['future'],
      python_requires=">3.4",
      package_data={'nifpga': ['VERSION']},
      author="National Instruments",
      url="https://github.com/ni/nifpga-python",
      license="MIT",
      classifiers=[
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Developers",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "License :: OSI Approved :: MIT License",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Human Machine Interfaces",
        "Topic :: Software Development :: Embedded Systems",
        "Topic :: System :: Hardware",
        "Topic :: System :: Hardware :: Hardware Drivers"]
      )

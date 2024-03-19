from setuptools import setup, find_packages

setup(
    name='tabviz',
    version='1.1.0',
    packages=find_packages(),
    package_data={'tabviz': ['static/*']},
    include_package_data=True,
    author='Ayush Dhiman',
    author_email='ayushdhiman272@gmail.com',
    description='Description of your package',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/AyushDhimann/tabvizz',
    license='GNU',
    install_requires=[
        'tableauserverclient',
    ],
)

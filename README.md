<p align="center"> <a href="https://muscorpus.com/"><img height="100" src="./assets/muscorpus_logo.svg" alt="MusCorpus logo"></a> </p>

# MusCorpus – an engine for musical corpora 
MusCorpus is the heart of [muscorpus.com](https://muscorpus.com/) website, aimed to bring the musical search to the academics and common users.

## Installation

We rely on `basexhttp` Docker image from BaseX and strongly recommend to set up our engine using `mamba` or `conda`.
* For starters, clone this repository and enter the directory: `git clone https://github.com/muscorpus/MusCorpus && cd MusCorpus`
* Unarchive the musical data: `tar -xzf basex_data.tar.gz`
* Install the required files via conda-forge: `mamba install -yq -c conda-forge --file conda_requirements.txt`
* Then proceed with installing packages not available via `conda-forge`: `pip install -q -r requirements.txt`
* Pull the `basexhttp` image: `docker pull basex/basexhttp`.
* Start the BaseX server: `docker run -ti --name basexhttp --publish 1984:1984 --publish 8984:8984--volume "$(pwd)/basex_data":/srv/basex/data basex/basexhttp:latest`.
* Finally, boot the web server: `gunicorn --bind 0.0.0.0:80 --bind 0.0.0.0:443 wsgi:app`


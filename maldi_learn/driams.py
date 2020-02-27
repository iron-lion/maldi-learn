'''
Main module for the DRIAMS dataset. Contains general exploration classes
and loaders.
'''

import dotenv
import os

import numpy as np
import pandas as pd

from maldi_learn.data import MaldiTofSpectrum
from maldi_learn.preprocessing.generic import LabelEncoder

# Pulls in the environment variables in order to simplify the access to
# the root directory.
dotenv.load_dotenv()

DRIAMS_ROOT = os.getenv('DRIAMS_ROOT')

_metadata_columns = ['code', 'bruker_organism_best_match', 'species']


class DRIAMSDatasetExplorer:
    def __init__(self, root=DRIAMS_ROOT):
        self.root = root

    def _get_available_sites(self):
        for _, dirs, _ in os.walk(self.root):
            sites = sorted(dirs)
            break
        return sites

    def _is_site_valid(self, site):
        '''
        Checks whether a specified site is valid. A site is considered
        valid if there is at least one ID file and at least one
        spectrum, either pre-processed or raw.

        Parameters
        ----------

            site:
                Name of the site to query. The function will build the
                necessary path to access the site automatically.

        Returns
        -------

        True if the site is valid according to the criterion specified
        above.
        '''

        path = os.path.join(self.root, site)

        for _, dirs, _ in os.walk(path):

            # Check whether ID directory exists
            if 'id' not in dirs:
                return False

            # Invalid if neither `preprocessed` nor `raw` exists as
            # a directory.`
            if 'preprocessed' not in dirs and 'raw' not in dirs:
                return False

            break

        # ID directory exists and at least one of `preprocessed` or
        # `raw` exists as well. Check all available IDs next.
        if not self._check_id_files(os.path.join(path, 'id')):
            return False

        return True

    def _check_id_files(self, id_directory):

        n_dirs = 0
        filenames = []

        for root, dirs, files in os.walk(id_directory):
            n_dirs += len(dirs)

            filenames.extend([os.path.join(root, f)
                for f in files if not f.startswith('.')]
            )

        # TODO: raise warning; each directory must contain a single file
        # only
        if n_dirs != len(filenames):
            return False

        # If we only get valid ID files, there must not be a `False`
        # entry in the list.
        valid = [self._is_id_valid(f) for f in filenames]
        return False not in valid

    def _is_id_valid(self, id_file):
        if not os.path.exists(id_file):
            return False

        try:
            df = pd.read_csv(id_file, low_memory=False)

            if 'code' not in df.columns:
                return False

        # Any error will make sure that this ID file is *not* valid
        except:
            return False

        # If we made it this far, the file is sufficiently well-formed
        # to not destroy everything.
        return True

    def _get_available_years(self, site):

        path = os.path.join(self.root, site)
        for _, dirs, files in os.walk(path):
            years = sorted(dirs)
            break

        # TODO: check whether spectrum information is available and
        # if each year has at least a single spectrum associated to
        # it.
        return years

    def _get_available_antibiotics(self, site, year):
        '''
        Queries a given site for the antibiotics that are available in
        it and returns them.

        Parameters
        ----------

        site:
            Identifier of the site that is to be queried. The function
            will build the paths accordingly.

        year:
            Year for which the given site should be queried. The
            function will build the paths accordingly.

        Returns
        -------

        List of antibiotic names, sorted in alphabetical order.
        '''

        path = os.path.join(
                self.root,
                site,
                'id',
                year,
                f'{year}_clean.csv'
        )

        df = pd.read_csv(path)
        antibiotics = [c for c in df.columns if c[0].isupper()]
        antibiotics = [a for a in antibiotics if 'Unnamed' not in a]

        return sorted(antibiotics)

    def available_antibiotics(self, site):
        """Return all available antibiotics for a given site.

        Returns
        -------
        All available antibiotics for the given site, in a `dict` whose
        keys represent the available years, and whose values represent
        the antibiotics.
        """
        return {
            year: self._get_available_antibiotics(site, year)
            for year in self.available_years(site)
        }

    def available_years(self, site):
        return self._get_available_years(site)

    @property
    def available_sites(self):
        return self._get_available_sites()



class DRIAMSDataset:
    
    def __init__(self, X, y):
        """
        X: 
            List of MaldiTofSpectra objects.
        y:  
            Metadata Pandas dataframe. Columns with antimicrobial
            information are indicated by capitalized header.

        """
        # checks if input is valid
        assert len(X) == y.shape[0]
        
        self.X = X
        self.y = y

    @property
    def is_multitask(self):
        n_cols = [c for c in self.y.columns if c not in _metadata_columns]
        return n_cols != 1
    
    @property
    def n_samples(self):
        return self.y.shape[0] 

    @property
    def n_label_avail(self):
        return self.y.loc[:, [col for col in self.y.columns if col not in
            _metadata_columns]].isna().sum(axis=0)

    # TODO implement
    @property
    def class_ratio(self):
        # return dict with label as key, and class fraction as value
        return fraq_dict
    
    # TODO implement
    def to_numpy(self): 
        # return y as numpy array as imput for classification
        y_numpy = self.y.to_numpy()
        return y_numpy

def load_driams_dataset(
    root,
    site,
    year,
    species,
    antibiotics,
    encoder=None,
    handle_missing_resistance_measurements='remove_if_all_missing',
    load_raw=False
):
    """Load DRIAMS data set for a specific site and specific year.

    This is the main loading function for interacting with DRIAMS
    datasets. Given required information about a site, a year, and
    a list of antibiotics, this function loads a dataset, handles
    missing values, and returns a `DRIAMSDataset` class instance.

    Notice that no additional post-processing will be performed. The
    spectra might thus have different lengths are not directly suitable
    for downstream processing in, say, a `scikit-learn` pipeline.

    Parameters
    ----------

    root:
        Root path to the DRIAMS dataset folder.

    site:
        Identifier of a site, such as `DRIAMS-A`.

    year:
        Identifier for the year, such as `2015`.

    species:
        Identifier for the species, such as *Staphylococcus aureus*.

    antibiotics:
        Identifier for the antibiotics to use, such as *Ciprofloxacin*.
        Can be either a `list` of strings or a single `str`, in which
        case only a single antibiotic will be loaded.

    encoder:
        If set, provides a mechanism for encoding labels into numbers.
        This will be applied *prior* to the missing value handling, so
        it is a simple strategy to remove invalid values. If no encoder
        is set, only missing values in the original data will be
        handled.

        Suitable values for `encoder` are instances of the
        `DRIAMSLabelEncoder` class, which performs our preferred
        encoding of labels.

    handle_missing_resistance_measurements:
        Strategy for handling missing resistance measurements. Can be
        one of the following:

            'remove_if_all_missing'
            'remove_if_any_missing'
            'keep'

    load_raw:
        If set, loads the *raw* spectra instead of the pre-processed
        one. This has no bearing whatsoever on the labels and metadata
        and merely changes the resulting spectra. If not set, loads
        the pre-processed spectra instead.

    Returns
    -------

    Instance of `DRIAMSDataset`, containing all loaded spectra.
    """
    if load_raw:
        spectra_type = 'raw'
    else:
        spectra_type = 'preprocessed'

    path_X = os.path.join(root, site, spectra_type, year)
    id_file = os.path.join(root, site, 'id', year, f'{year}_clean.csv')

    # Metadata contains all information that we have about the
    # individual spectra and the selected antibiotics.
    metadata = _load_metadata(
        id_file,
        species,
        antibiotics,
        encoder,
        handle_missing_resistance_measurements
    )

    # The codes are used to uniquely identify the spectra that we can
    # load. They are required for matching files and metadata.
    codes = metadata.code

    spectra_files = [
        os.path.join(path_X, f'{code}.txt') for code in codes
    ]

    spectra = [
        MaldiTofSpectrum(
            pd.read_csv(f, sep=' ', comment='#', engine='c').values
        ) for f in spectra_files
    ]

    # TODO doesn't return a DRIAMSDataset instance yet
    return spectra, metadata


def _load_metadata(
    filename,
    species,
    antibiotics,
    encoder,
    handle_missing_resistance_measurements
):

    # Ensures that we always get a list of antibiotics for subsequent
    # processing.
    if type(antibiotics) is not list:
        antibiotics = [antibiotics]

    assert handle_missing_resistance_measurements in [
            'remove_if_all_missing',
            'remove_if_any_missing',
            'keep'
    ]

    metadata = pd.read_csv(
                    filename,
                    low_memory=False,
                    na_values=['-'],
                    keep_default_na=True,
                )

    metadata = metadata.query('species == @species')

    # TODO make cleaner
    metadata = metadata[_metadata_columns + antibiotics]
    n_antibiotics = len(antibiotics)

    if encoder is not None:
        metadata = encoder.fit_transform(metadata)

    # handle_missing_values
    if handle_missing_resistance_measurements == 'remove_if_all_missing':
        na_values = metadata[antibiotics].isna().sum(axis='columns')
        metadata = metadata[na_values != n_antibiotics]
    elif handle_missing_resistance_measurements == 'remove_if_any_missing':
        na_values = metadata[antibiotics].isna().sum(axis='columns')
        metadata = metadata[na_values == 0]
    else:
        pass

    return metadata


class DRIAMSLabelEncoder(LabelEncoder):
    """Encoder for DRIAMS labels.

    Encodes antibiotic resistance measurements in a standardised manner.
    Specifically, *resistant* or *intermediate* measurements are will be
    converted to `1`, while *suspectible* measurements will be converted
    to `0`.
    """

    def __init__(self):
        """Create new instance of the encoder."""
        # These are the default encodings for the DRIAMS dataset. If
        # other values show up, they will not be handled; this is by
        # design.
        encodings = {
            'R': 1,
            'I': 1,
            'S': 0,
            'R(1)': np.nan,
            'L(1)': np.nan,
            'I(1)': np.nan,
            'I(1), S(1)': np.nan,
            'R(1), I(1)': np.nan,
            'R(1), S(1)': np.nan,
            'R(1), I(1), S(1)': np.nan
        }

        # Ignore the metadata columns to ensure that these values will
        # not be replaced anywhere else.
        super().__init__(encodings, _metadata_columns)

# HERE BE DRAGONS

explorer = DRIAMSDatasetExplorer('/Volumes/borgwardt/Data/DRIAMS')

print(explorer._get_available_antibiotics('DRIAMS-A', '2015'))

print(explorer.__dict__)
print(explorer.available_sites)
print(explorer.available_years)
print(explorer._is_site_valid('DRIAMS-A'))

spectra, df = load_driams_dataset(
            explorer.root,
            'DRIAMS-A',
            '2015',
            'Staphylococcus aureus',
            ['Ciprofloxacin', 'Penicillin'],
            encoder=DRIAMSLabelEncoder(),
            handle_missing_resistance_measurements='remove_if_all_missing',
)

<<<<<<< HEAD
dd = DRIAMSDataset(spectra, df)
print(dd.n_label_avail)

=======
print(df.to_numpy().shape)
print(df.to_numpy().dtype)
print(df.to_numpy()[0])
print(df)
>>>>>>> 54f1cc66ca941174b6922f32bc9df4a8ec70132d

print(explorer._get_available_antibiotics('DRIAMS-A', '2015'))

print(DRIAMSLabelEncoder().transform(df))

from maldi_learn.vectorization import BinningVectorizer

bv = BinningVectorizer(1000, min_bin=2000, max_bin=20000)

X = bv.fit_transform(spectra)
print(X.shape)

"""T1 FreeSurfer - Clinica Command Line Interface.
This file has been generated automatically by the `clinica generate template`
command line tool. See here for more details: https://gitlab.icm-institute.org/aramis/clinica/wikis/docs/InteractingWithClinica.
"""

import clinica.engine as ce

__author__ = "Junhao Wen"
__copyright__ = "Copyright 2016, The Aramis Lab Team"
__credits__ = ["Michael Bacci", "Junhao Wen"]
__license__ = "See LICENSE.txt file"
__version__ = "0.1.0"
__maintainer__ = "Junhao Wen"
__email__ = "junhao.Wen@inria.fr"
__status__ = "Development"

class T1FreeSurferCLI(ce.CmdParser):

    def define_name(self):
        """Define the sub-command name to run this pipelines.
        """
        self._name = 't1-freesurfer'

    def define_options(self):
        """Define the sub-command arguments
        """
        # default args created by template
        self._args.add_argument("bids_directory",
                                help='Path to the BIDS directory.')
        self._args.add_argument("caps_directory",
                                help='Path to the CAPS directory.')
        self._args.add_argument("-tsv", "--subjects_sessions_tsv",
                                help='TSV file containing the subjects with their sessions.')
        # Custom args added by developers
        self._args.add_argument("-ras", "--recon_all_args",
                                help='additional flags for recon-all command line, default will be -qcache')
        self._args.add_argument("-wd", "--working_directory",
                                help='Temporary directory to store pipelines intermediate results')
        self._args.add_argument("-np", "--n_procs", type=int,
                                help='Number of cores used to run in parallel')

    def run_pipeline(self, args):
        """
        Run the pipelines with defined args
        """
        from t1_freesurfer_pipeline import T1FreeSurfer
        from tempfile import mkdtemp

        pipeline = T1FreeSurfer(
            # pass these args by the class attribute itself
            bids_directory=self.absolute_path(args.bids_directory),
            caps_directory=self.absolute_path(args.caps_directory),
            tsv_file=self.absolute_path(args.subjects_sessions_tsv))

        pipeline.parameters = {
            # pass these args by using self.parameters in a dictionary
            'recon_all_args': args.recon_all_args or '-qcache'
        }

        # make sure if working_directory is not defined, using a temp folder to the working directory.
        if args.working_directory is None:
            args.working_directory = mkdtemp()
        pipeline.base_dir = self.absolute_path(args.working_directory)

        # run the pipelines in n_procs cores based on your computation power.
        if args.n_procs:
            #pipelines.write_graph()
            pipeline.run(plugin='MultiProc', plugin_args={'n_procs': args.n_procs})
        else:
            #pipelines.write_graph()
            pipeline.run()
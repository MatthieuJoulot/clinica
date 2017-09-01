
import os
from os import path
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, StratifiedShuffleSplit
from multiprocessing.pool import ThreadPool

from clinica.pipeline.machine_learning import base


class KFoldCV(base.MLValidation):

    def __init__(self, ml_algorithm):
        self._ml_algorithm = ml_algorithm
        self._fold_results = []
        self._classifier = None
        self._best_params = None
        self._cv = None

    def validate(self, y, n_folds=10, n_threads=15):

        skf = StratifiedKFold(n_splits=n_folds, shuffle=True)
        self._cv = list(skf.split(np.zeros(len(y)), y))
        async_pool = ThreadPool(n_threads)
        async_result = {}

        for i in range(n_folds):

            train_index, test_index = self._cv[i]
            async_result[i] = async_pool.apply_async(self._ml_algorithm.evaluate, (train_index, test_index))

        async_pool.close()
        async_pool.join()

        for i in range(n_folds):
            self._fold_results.append(async_result[i].get())

        self._classifier, self._best_params = self._ml_algorithm.apply_best_parameters(self._fold_results)

        return self._classifier, self._best_params, self._fold_results

    def save_results(self, output_dir):
        if self._fold_results is None:
            raise Exception("No results to save. Method validate() must be run before save_results().")

        subjects_folds = []
        results_folds = []
        container_dir = path.join(output_dir, 'folds')

        if not path.exists(container_dir):
            os.makedirs(container_dir)

        for i in range(len(self._fold_results)):
            subjects_df = pd.DataFrame({'y': self._fold_results[i]['y'],
                                        'y_hat': self._fold_results[i]['y_hat'],
                                        'y_index': self._fold_results[i]['y_index']})
            subjects_df.to_csv(path.join(container_dir, 'subjects_fold-' + str(i) + '.tsv'),
                               index=False, sep='\t', encoding='utf-8')
            subjects_folds.append(subjects_df)

            results_df = pd.DataFrame({'balanced_accuracy': self._fold_results[i]['evaluation']['balanced_accuracy'],
                                       'auc': self._fold_results[i]['auc'],
                                       'accuracy': self._fold_results[i]['evaluation']['accuracy'],
                                       'sensitivity': self._fold_results[i]['evaluation']['sensitivity'],
                                       'specificity': self._fold_results[i]['evaluation']['specificity'],
                                       'ppv': self._fold_results[i]['evaluation']['ppv'],
                                       'npv': self._fold_results[i]['evaluation']['npv']}, index=['i', ])
            results_df.to_csv(path.join(container_dir, 'results_fold-' + str(i) + '.tsv'),
                              index=False, sep='\t', encoding='utf-8')
            results_folds.append(results_df)

        all_subjects = pd.concat(subjects_folds)
        all_subjects.to_csv(path.join(output_dir, 'subjects.tsv'),
                            index=False, sep='\t', encoding='utf-8')

        all_results = pd.concat(results_folds)
        all_results.to_csv(path.join(output_dir, 'results.tsv'),
                           index=False, sep='\t', encoding='utf-8')

        mean_results = pd.DataFrame(all_results.apply(np.nanmean).to_dict(), columns=all_results.columns, index=[0, ])
        mean_results.to_csv(path.join(output_dir, 'mean_results.tsv'),
                            index=False, sep='\t', encoding='utf-8')


class RepeatedKFoldCV(base.MLValidation):

    def __init__(self, ml_algorithm):
        self._ml_algorithm = ml_algorithm
        self._repeated_fold_results = []
        self._classifier = None
        self._best_params = None
        self._cv = None

    def validate(self, y, n_iterations=100, n_folds=10, n_threads=15):

        async_pool = ThreadPool(n_threads)
        async_result = {}
        self._cv = []

        for r in range(n_iterations):
            skf = StratifiedKFold(n_splits=n_folds, shuffle=True)
            self._cv.append(list(skf.split(np.zeros(len(y)), y)))
            async_result[r] = {}
            self._repeated_fold_results.append([])

            for i in range(n_folds):

                train_index, test_index = self._cv[r][i]
                async_result[r][i] = async_pool.apply_async(self._ml_algorithm.evaluate, (train_index, test_index))

        async_pool.close()
        async_pool.join()
        for r in range(n_iterations):
            for i in range(n_folds):
                self._repeated_fold_results[r].append(async_result[r][i].get())

        # TODO Find a better way to estimate best parameter
        flat_results = [result for fold in self._repeated_fold_results for result in fold]
        self._classifier, self._best_params = self._ml_algorithm.apply_best_parameters(flat_results)

        return self._classifier, self._best_params, self._repeated_fold_results

    def save_results(self, output_dir):
        if self._repeated_fold_results is None:
            raise Exception("No results to save. Method validate() must be run before save_results().")

        all_results_list = []
        all_subjects_list = []
        
        for iteration in range(len(self._repeated_fold_results)):

            iteration_dir = path.join(output_dir, 'iteration-' + str(iteration))
            if not path.exists(iteration_dir):
                os.makedirs(iteration_dir)

            iteration_subjects_list = []
            iteration_results_list = []
            folds_dir = path.join(iteration_dir, 'folds')

            if not path.exists(folds_dir):
                os.makedirs(folds_dir)

            for i in range(len(self._repeated_fold_results[iteration])):
                subjects_df = pd.DataFrame({'y': self._repeated_fold_results[iteration][i]['y'],
                                            'y_hat': self._repeated_fold_results[iteration][i]['y_hat'],
                                            'y_index': self._repeated_fold_results[iteration][i]['y_index']})
                subjects_df.to_csv(path.join(folds_dir, 'subjects_fold-' + str(i) + '.tsv'),
                                   index=False, sep='\t', encoding='utf-8')
                iteration_subjects_list.append(subjects_df)

                results_df = pd.DataFrame(
                    {'balanced_accuracy': self._repeated_fold_results[iteration][i]['evaluation']['balanced_accuracy'],
                     'auc': self._repeated_fold_results[iteration][i]['auc'],
                     'accuracy': self._repeated_fold_results[iteration][i]['evaluation']['accuracy'],
                     'sensitivity': self._repeated_fold_results[iteration][i]['evaluation']['sensitivity'],
                     'specificity': self._repeated_fold_results[iteration][i]['evaluation']['specificity'],
                     'ppv': self._repeated_fold_results[iteration][i]['evaluation']['ppv'],
                     'npv': self._repeated_fold_results[iteration][i]['evaluation']['npv']}, index=['i', ])
                results_df.to_csv(path.join(folds_dir, 'results_fold-' + str(i) + '.tsv'),
                                  index=False, sep='\t', encoding='utf-8')
                iteration_results_list.append(results_df)

            iteration_subjects_df = pd.concat(iteration_subjects_list)
            iteration_subjects_df.to_csv(path.join(iteration_dir, 'subjects.tsv'),
                                         index=False, sep='\t', encoding='utf-8')
            all_subjects_list.append(iteration_subjects_df)

            iteration_results_df = pd.concat(iteration_results_list)
            iteration_results_df.to_csv(path.join(iteration_dir, 'results.tsv'),
                                        index=False, sep='\t', encoding='utf-8')

            mean_results_df = pd.DataFrame(iteration_results_df.apply(np.nanmean).to_dict(),
                                           columns=iteration_results_df.columns, index=[0, ])
            mean_results_df.to_csv(path.join(iteration_dir, 'mean_results.tsv'),
                                   index=False, sep='\t', encoding='utf-8')
            all_results_list.append(mean_results_df)

        all_subjects_df = pd.concat(all_subjects_list)
        all_subjects_df.to_csv(path.join(output_dir, 'subjects.tsv'),
                               index=False, sep='\t', encoding='utf-8')

        all_results_df = pd.concat(all_results_list)
        all_results_df.to_csv(path.join(output_dir, 'results.tsv'),
                              index=False, sep='\t', encoding='utf-8')

        mean_results_df = pd.DataFrame(all_results_df.apply(np.nanmean).to_dict(),
                                       columns=all_results_df.columns, index=[0, ])
        mean_results_df.to_csv(path.join(output_dir, 'mean_results.tsv'),
                               index=False, sep='\t', encoding='utf-8')


class RepeatedSplit(base.MLValidation):

    def __init__(self, ml_algorithm, n_iterations=100, test_size=0.3):
        self._ml_algorithm = ml_algorithm
        self._split_results = []
        self._classifier = None
        self._best_params = None
        self._cv = None
        self._n_iterations = n_iterations
        self._test_size = test_size
        self._resampled_t = None
        self._corrected_resampled_t = None

    def validate(self, y, n_threads=15):

        splits = StratifiedShuffleSplit(n_splits=self._n_iterations, test_size=self._test_size)
        self._cv = list(splits.split(np.zeros(len(y)), y))
        async_pool = ThreadPool(n_threads)
        async_result = {}

        for i in range(self._n_iterations):

            train_index, test_index = self._cv[i]
            async_result[i] = async_pool.apply_async(self._ml_algorithm.evaluate, (train_index, test_index))
            print 'outer', i, async_result[i]
        async_pool.close()
        async_pool.join()

        for i in range(self._n_iterations):
            self._split_results.append(async_result[i].get())
        print self._split_results
        
        self._classifier, self._best_params = self._ml_algorithm.apply_best_parameters(self._split_results)
        print self._best_params
        return self._classifier, self._best_params, self._split_results

    def save_results(self, output_dir):
        if self._split_results is None:
            raise Exception("No results to save. Method validate() must be run before save_results().")

        all_results_list = []
        all_subjects_list = []

        for iteration in range(len(self._split_results)):

            iteration_dir = path.join(output_dir, 'iteration-' + str(iteration))
            if not path.exists(iteration_dir):
                os.makedirs(iteration_dir)

            # iteration_subjects_list = []
            # iteration_results_list = []
            # folds_dir = path.join(iteration_dir, 'folds')

            # if not path.exists(folds_dir):
            #     os.makedirs(folds_dir)

            # for i in range(len(self._split_results[iteration])):
            #     subjects_df = pd.DataFrame({'y': self._split_results[iteration][i]['y'],
            #                                 'y_hat': self._split_results[iteration][i]['y_hat'],
            #                                 'y_index': self._split_results[iteration][i]['y_index']})
            #     subjects_df.to_csv(path.join(folds_dir, 'subjects_fold-' + str(i) + '.tsv'),
            #                        index=False, sep='\t', encoding='utf-8')
            #     iteration_subjects_list.append(subjects_df)
            #
            #     results_df = pd.DataFrame(
            #         {'balanced_accuracy': self._split_results[iteration][i]['evaluation']['balanced_accuracy'],
            #          'auc': self._split_results[iteration][i]['auc'],
            #          'accuracy': self._split_results[iteration][i]['evaluation']['accuracy'],
            #          'sensitivity': self._split_results[iteration][i]['evaluation']['sensitivity'],
            #          'specificity': self._split_results[iteration][i]['evaluation']['specificity'],
            #          'ppv': self._split_results[iteration][i]['evaluation']['ppv'],
            #          'npv': self._split_results[iteration][i]['evaluation']['npv']}, index=['i', ])
            #     results_df.to_csv(path.join(folds_dir, 'results_fold-' + str(i) + '.tsv'),
            #                       index=False, sep='\t', encoding='utf-8')
            #     iteration_results_list.append(results_df)

            iteration_subjects_df = pd.DataFrame({'y': self._split_results[iteration]['y'],
                                                  'y_hat': self._split_results[iteration]['y_hat'],
                                                  'y_index': self._split_results[iteration]['y_index']})
            iteration_subjects_df.to_csv(path.join(iteration_dir, 'subjects.tsv'),
                                         index=False, sep='\t', encoding='utf-8')
            all_subjects_list.append(iteration_subjects_df)

            iteration_results_df = pd.DataFrame(
                    {'balanced_accuracy': self._split_results[iteration]['evaluation']['balanced_accuracy'],
                     'auc': self._split_results[iteration]['auc'],
                     'accuracy': self._split_results[iteration]['evaluation']['accuracy'],
                     'sensitivity': self._split_results[iteration]['evaluation']['sensitivity'],
                     'specificity': self._split_results[iteration]['evaluation']['specificity'],
                     'ppv': self._split_results[iteration]['evaluation']['ppv'],
                     'npv': self._split_results[iteration]['evaluation']['npv']}, index=['i', ])
            iteration_results_df.to_csv(path.join(iteration_dir, 'results.tsv'),
                                        index=False, sep='\t', encoding='utf-8')

            mean_results_df = pd.DataFrame(iteration_results_df.apply(np.nanmean).to_dict(),
                                           columns=iteration_results_df.columns, index=[0, ])
            mean_results_df.to_csv(path.join(iteration_dir, 'mean_results.tsv'),
                                   index=False, sep='\t', encoding='utf-8')
            all_results_list.append(mean_results_df)

        all_subjects_df = pd.concat(all_subjects_list)
        all_subjects_df.to_csv(path.join(output_dir, 'subjects.tsv'),
                               index=False, sep='\t', encoding='utf-8')

        all_results_df = pd.concat(all_results_list)
        all_results_df.to_csv(path.join(output_dir, 'results.tsv'),
                              index=False, sep='\t', encoding='utf-8')

        mean_results_df = pd.DataFrame(all_results_df.apply(np.nanmean).to_dict(),
                                       columns=all_results_df.columns, index=[0, ])
        mean_results_df.to_csv(path.join(output_dir, 'mean_results.tsv'),
                               index=False, sep='\t', encoding='utf-8')

        # results_dict = {'balanced_accuracy': np.nanmean([r['evaluation']['balanced_accuracy'] for r in self._split_results]),
        #                 'auc': np.nanmean([r['auc'] for r in self._split_results]),
        #                 'accuracy': np.nanmean([r['evaluation']['accuracy'] for r in self._split_results]),
        #                 'sensitivity': np.nanmean([r['evaluation']['sensitivity'] for r in self._split_results]),
        #                 'specificity': np.nanmean([r['evaluation']['specificity'] for r in self._split_results]),
        #                 'ppv': np.nanmean([r['evaluation']['ppv'] for r in self._split_results]),
        #                 'npv': np.nanmean([r['evaluation']['npv'] for r in self._split_results])}
        #
        # # t1_df = pd.DataFrame(columns=t1_col_df)
        # # t1_df = t1_df.append(row_to_append, ignore_index=True)
        #
        # results_df = pd.DataFrame(results_dict, index=['i', ])
        # results_df.to_csv(path.join(output_dir, 'results.tsv'),
        #                   index=False, sep='\t', encoding='utf-8')
        #
        # subjects_folds = []
        # container_dir = path.join(output_dir, 'iterations')
        # if not path.exists(container_dir):
        #     os.makedirs(container_dir)
        # for i in range(len(self._split_results)):
        #     subjects_df = pd.DataFrame({'y': self._split_results[i]['y'],
        #                                 'y_hat': self._split_results[i]['y_hat'],
        #                                 'y_index': self._split_results[i]['y_index']})
        #
        #     subjects_df.to_csv(path.join(container_dir, 'subjects_iteration-' + str(i) + '.tsv'),
        #                        index=False, sep='\t', encoding='utf-8')
        #
        #     subjects_folds.append(subjects_df)
        #
        # all_subjects = pd.concat(subjects_folds)
        # all_subjects.to_csv(path.join(output_dir, 'subjects.tsv'),
        #                     index=False, sep='\t', encoding='utf-8')

    def compute_variance(self):
        # compute average test error
        num_split = len(self._split_results)  # J in the paper
        test_error_split = np.zeros((num_split, 1))  # this list will contain the list of mu_j hat for j = 1 to J
        for i in range(num_split):
            test_error_split[i] = self._compute_average_test_error(self._split_results[i]['y'],
                                                                   self._split_results[i]['y_hat'])
        
        # compute mu_{n_1}^{n_2}
        average_test_error = np.mean(test_error_split)
        
        # compute variance (point 2 and 6 of Nadeau's paper)
        self._resampled_t = np.linalg.norm(test_error_split - average_test_error)**2/(num_split - 1)
        self._corrected_resampled_t = (1/num_split + self._test_size/(1 - self._test_size)) * self._resampled_t

        return self._resampled_t, self._corrected_resampled_t

    def _compute_average_test_error(self, y_list, yhat_list):
        # return the average test error (denoted mu_j hat)
        return len(np.where(y_list != yhat_list)[0])/len(y_list)
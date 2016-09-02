#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: gridded_benchmarks.py
Author: naught101
Email: naught101@email.com
Github: https://github.com/naught101/
Description: TODO: File description

Usage:
    gridded_benchmarks.py generate <benchmark> <forcing> [--years=<years>]
    gridded_benchmarks.py (-h | --help | --version)

Options:
    benchmark:       1lin, 3km27, 3km233
    forcing:         PRINCETON, CRUNCEP, WATCH_WFDEI, GSWP3
    --years=<years>  2012-2013, python indexing style
    -h, --help       Show this screen and exit.
"""

from docopt import docopt

import os
import datetime

import numpy as np
import xarray as xr

import pals_utils.data as pud

from ubermodel.data import get_sites, get_data_dir
from ubermodel.gridded_datasets import get_dataset_data, get_dataset_freq
from ubermodel.models import get_benchmark_model, get_model_vars


def predict_gridded(model, dataset_data, flux_vars, datafreq=None):
    """predict model results for gridded data

    :model: TODO
    :data: TODO
    :returns: TODO

    """
    # set prediction metadata
    prediction = dataset_data[list(dataset_data.coords)]

    # Arrays like (var, lon, lat, time)
    result = np.full([len(flux_vars),
                      dataset_data.dims['lon'],
                      dataset_data.dims['lat'],
                      dataset_data.dims['time']],
                     np.nan)

    print("lon:    ", end='', flush=True)

    for lon in range(len(dataset_data['lon'])):
        print("\b\b\b\b\b", str(lon).rjust(4), end='', flush=True)
        for lat in range(len(dataset_data['lat'])):
            # If data has fill values, only predict with masked data
            first_step = dataset_data.isel(time=0, lat=lat, lon=lon).to_array()
            if (np.all(-1e8 < first_step) and np.all(first_step < 1e8)):
                if datafreq is not None:
                    result[:, lon, lat, :] = model.predict(
                        dataset_data.isel(lat=lat, lon=lon).to_array().T,
                        datafreq=datafreq
                    ).T
                else:
                    result[:, lon, lat, :] = model.predict(
                        dataset_data.isel(lat=lat, lon=lon).to_array().T
                    ).T
    print("")

    for i, fv in enumerate(flux_vars):
        prediction.update(
            {fv: xr.DataArray(result[i, :, :, :],
                              dims=['lon', 'lat', 'time'],
                              coords=dataset_data.coords
                              )
             }
        )

    return prediction


def xr_add_attributes(ds, benchmark, dataset, sites):

    ds.attrs["Model name"] = benchmark
    met_vars, flux_vars = get_model_vars(benchmark)
    ds.attrs["Forcing_variables"] = ', '.join(met_vars)
    ds.attrs["Forcing_dataset"] = dataset
    ds.attrs["Training_dataset"] = "Fluxnet_1.4"
    ds.attrs["Training_sites"] = ', '.join(sites)
    ds.attrs["Production_time"] = datetime.datetime.now().isoformat()
    ds.attrs["Production_source"] = "gridded_benchmarks.py"
    ds.attrs["PALS_dataset_version"] = "1.4"
    ds.attrs["Contact"] = "ned@nedhaughton.com"


def fit_and_predict(benchmark, dataset, years='2012-2013'):
    """Fit a benchmark to some PALS files, then generate an output matching a gridded dataset
    """

    met_vars, flux_vars = get_model_vars(benchmark)

    model = get_benchmark_model(benchmark)

    sites = get_sites()

    years = [int(s) for s in years.split('-')]

    print("Loading fluxnet data for %d sites" % len(sites))
    met_data = pud.get_met_df(sites, met_vars, qc=True, name=True)
    flux_data = pud.get_flux_df(sites, flux_vars, qc=True)

    print("Fitting model {b} using {m} to predict {f}".format(
        b=benchmark, m=met_vars, f=flux_vars))
    model.fit(met_data, flux_data)

    # prediction datasets
    outdir = "{d}/gridded_benchmarks/{b}_{ds}".format(d=get_data_dir(), b=benchmark, ds=dataset)
    os.makedirs(outdir, exist_ok=True)
    outfile_tpl = outdir + "/{b}_{d}_{v}_{y}.nc"
    for year in range(*years):

        print("Loading Forcing data for", year)
        data = get_dataset_data(dataset, met_vars, year)
        print("Predicting", year, end=': ', flush=True)
        if "lag" in benchmark:
            result = predict_gridded(model, data, flux_vars, datafreq=get_dataset_freq(dataset))
        else:
            result = predict_gridded(model, data, flux_vars)

        xr_add_attributes(result, benchmark, dataset, sites)
        for fv in flux_vars:
            filename = outfile_tpl.format(b=benchmark, d=dataset, v=fv, y=year)
            print("saving to ", filename)
            result[[fv]].to_netcdf(filename, encoding={fv: {'dtype': 'float32'}})

    return


def main(args):

    if args['generate']:
        if args['--years'] is not None:
            fit_and_predict(args['<benchmark>'], args['<forcing>'], args['--years'])
        else:
            fit_and_predict(args['<benchmark>'], args['<forcing>'])
    return


if __name__ == '__main__':
    args = docopt(__doc__)

    main(args)

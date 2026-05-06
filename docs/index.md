# sBlot Documentation

## Introduction

This document explains how to use the `sBlot` package to visualise the results of an `sBayes` analysis.

`sBayes` is a clustering method that identifies groups with similar features while accounting for similarities due to known confounders. 

### Static visualisations
Users can create five main types of static plots:

1. [**Weight plots**](plots/weights.md) visualise the weights assigned to each confounder and each of the clusters.
2. [**Preference plots**](plots/preferences.md) show the distribution of a feature in each cluster and in each group within each confounder.
3. [**Pie plots**](plots/pies.md) show the membership of objects to clusters.
4. [**LOO plots**](plots/loo.md) compare the Pareto-Smoothed Importance Sampling Leave-One-Out Cross-Validation (PSIS-LOO) for models with different numbers of clusters.
5. [**Maps**](plots/map.md) visualise the spatial allocation of objects to clusters.

Users define all plotting parameters in two configuration files:

- [**`config_plot.yaml`**](configuration/config_plot.md) specifies the input data and results of the `sBayes` analysis to visualise, the plots to generate, and the analytical tasks to perform for each plot.
- [**`config_style.yaml`**](configuration/config_style.md) defines the graphical style, including colors and font sizes.

Typically, users provide all parameters in the `config_plot.yaml` file, but use the pre-set style parameters for `config_style.yaml`, modifying only selected parameters as needed.

### Interactive explorer

Alternatively, users can also explore the posterior distribution in an [interactive explorer](interactive.md). 

## Documentation

|                                                      |                                      |
|------------------------------------------------------|--------------------------------------|
| [Installation](installation.md)                      | How to install sBlot                 |
| [Quick start](quickstart.md)                         | Creating plots in a few steps        |
| [Plot types](plots/overview.md)                      | Overview of all available plot types |
| [Plot configuration](configuration/config_plot.md)   | Full `config_plot.yaml` reference    |
| [Style configuration](configuration/config_style.md) | Full `config_style.yaml` reference   |
| [Interactive explorer](interactive.md)               | Browser-based posterior exploration  |
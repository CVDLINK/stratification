# Stratification FC App


## What it is

A [FeatureCloud](https://featurecloud.ai/) app that
builds a **balanced / stratified cohort** from OMOP CDM data (read from parquet snapshots) or local
CSV, for training AI models in CVDLINK.<br />
Given a configured set of features (categorical, numerical-as-bins, multi-label categorical) and
target class fractions, the app resamples an input dataset (over- or under-sampling) into a cohort
matching the requested distribution while honoring per-class minimums.<br />
It runs identically on the FeatureCloud coordinator and every participant.


## Status

`prototype`  <!-- one of: experimental | prototype | stable | archived | data-only -->

## Inputs / outputs — *for a model or tool*

- **Input:**
    - **`config.yml`**: FeatureCloud workflow config file<br />
    ```yaml
    #example
    stratification:
      input:
        config: stratification-config.yml   # stratification config file, resolved relative to INPUT_DIR
        data_dir: /mnt/exports              # parquet data directory (optional; see below)
        metadata: metadata.json             # ETL data-discovery metadata JSON (optional; see below)
      output:                               # output file names, written under OUTPUT_DIR
        stratified: ptbxl_database_strat.csv
        raw: raw_unbalanced_dataset.csv
        dataset_stats: dataset_stats.csv
        stratified_stats: stratified_stats.csv
        sampling_plan: sampling_plan.csv
        run_config: stratification_config.yml  # resolved run config (optional; see below)
    ```
    - Parquet files exported by OMOP CDM PostgreSQL
- **Output:**
    - **`stratification_performance_report_v<version>.md`**: Comprehensive markdown report with summary tables and detailed analysis
    - **`{dataset_name}_stratified_data.csv`**: Stratified datasets for each test case
    - **`{dataset_name}_dataset_stats_df.csv`**: Original dataset statistics
    - **`{dataset_name}_stratified_stats_df.csv`**: Stratified dataset statistics
    - **`{dataset_name}_stratified_extended_df.csv`**: Extended stratified data with additional metadata


## Install / run

This app is supposed to be registered in FeatureCloud App Store and used in [FeatureCloud workflow](https://featurecloud.ai/assets/developer_documentation/workflow.html).

## Maintainer

Veracell Oy · amanda.laurila@veracell.com

## How to cite

Once this repo is archived to Zenodo, add the DOI here (citation metadata lives in `.zenodo.json`).

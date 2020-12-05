import math
from copy import deepcopy

from .blocking import cartesian_block
from .gammas import add_gammas
from .maximisation_step import run_maximisation_step
from .params import Params

from pyspark.sql.dataframe import DataFrame
from pyspark.sql.session import SparkSession


def _num_target_rows_to_rows_to_sample(target_rows):
    # Number of rows generated by cartesian product is
    # n(n-1)/2, where n is input rows
    # We want to set a target_rows = t, the number of
    # rows generated by Splink and find out how many input rows
    # we need to generate targer rows
    #     Solve t = n(n-1)/2 for n
    #     https://www.wolframalpha.com/input/?i=Solve%5Bt%3Dn+*+%28n+-+1%29+%2F+2%2C+n%5D
    sample_rows = 0.5 * ((8 * target_rows + 1) ** 0.5 + 1)
    return math.ceil(sample_rows)


def estimate_u_values(
    settings: dict,
    df: DataFrame,
    target_rows: int,
    spark: SparkSession,
):
    # Preserve settings as provided
    orig_settings = deepcopy(settings)

    # Do not modify settings object provided by user either
    settings = deepcopy(settings)

    count_rows = df.count()
    sample_size = _num_target_rows_to_rows_to_sample(target_rows)

    proportion = sample_size / count_rows

    if proportion >= 1.0:
        proportion = 1.0

    df_s = df.sample(False, proportion)

    df_comparison = cartesian_block(settings, spark, df=df_s)
    df_gammas = add_gammas(df_comparison, settings, spark)

    df_e_product = df_gammas.withColumn("match_probability", f.lit(0.0))

    params = Params(settings, spark)
    run_maximisation_step(df_e_product, params, spark)
    new_settings = params.get_settings_with_current_params()

    for i, col in enumerate(orig_settings["comparison_columns"]):
        u_probs = new_settings["comparison_columns"][i]["u_probabilities"]
        col["u_probabilities"] = u_probs

    new_settings

import glob
import math
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import matplotlib.ticker as tkr
import os
import pandas as pd
import MvsoModel
import sys

# INIT


def get_most_recent_entry(search_dir):
    """ Return most recently modified entry from given directory.

    Args:
        search_dir: an absolute or relative path to a directory

    Returns:
        The file/folder in search_dir that has the most recent 'modified'
        datetime.
    """
    entries = glob.glob(os.path.join(search_dir, "*"))
    entries.sort(key=lambda x: os.path.getmtime(x))
    return entries[-1]


def glob_result_files(folder_name):
    """ Glob result spreadsheets from specified folder.

    Args:
        folder_name: an absolute or relative path to a directory

    Returns:
        list of filenames that match the pattern 'scenario_*.xlsx'
    """
    glob_pattern = os.path.join(folder_name, 'scenario_*.xlsx')
    result_files = sorted(glob.glob(glob_pattern))
    return result_files


def deduplicate_legend(handles, labels):
    """ Remove double entries from figure legend.

    Args:
        handles: list of legend entry handles
        labels: list of legend entry labels

    Returns:
        (handles, labels) tuple of lists with duplicate labels removed
    """
    new_handles = []
    new_labels = []
    for hdl, lbl in zip(handles, labels):
        if lbl not in new_labels:
            new_handles.append(hdl)
            new_labels.append(lbl)
    # also, sort both lists accordingly
    new_labels, new_handles = (list(t) for t
                               in zip(*sorted(zip(new_labels, new_handles))))
    return (new_handles, new_labels)


def group_hbar_plots(ax, group_size, inner_sep=None):
    """
    Args:
        ax: matplotlib axis
        group_size (int): how many bars to group together
        inner_sep (float): vertical spacing within group (optional)
    """
    handles, labels = ax.get_legend_handles_labels()
    bar_height = handles[0][0].get_height()  # assumption: all bars identical

    if not inner_sep:
        inner_sep = 0.5 * (1 - bar_height)

    for column, handle in enumerate(handles):
        for row, patch in enumerate(handle.patches):
            group_number, row_within_group = divmod(row, group_size)

            group_offset = (group_number * group_size
                            + 0.5 * (group_size - 1) * (1 - inner_sep)
                            - 0.5 * (group_size * bar_height))

            patch.set_y(row_within_group * (bar_height + inner_sep)
                        + group_offset)


def compare_scenarios(result_files, output_filename):
    """ Create report sheet and plots for given report spreadsheets.

    Args:
        result_files: a list of spreadsheet filenames generated by MvsoModel.report
        output_filename: a spreadsheet filename that the comparison is to be
                         written to

     Returns:
        Nothing

    To do:
        Don't use report spreadsheets, instead load pickled problem
        instances. This would make this function less fragile and dependent
        on the output format of MvsoModel.report().
    """

    # derive list of scenario names for column labels/figure captions
    scenario_names = [os.path.basename(rf)  # drop folder names, keep filename
                      .replace('_', ' ')  # replace _ with spaces
                      .replace('.xlsx', '')  # drop file extension
                      .replace('scenario ', '')  # drop 'scenario ' prefix
                      for rf in result_files]

    # find base scenario and put at first position
    try:
        base_scenario = scenario_names.index('base')
        result_files.append(result_files.pop(base_scenario))
        scenario_names.append(scenario_names.pop(base_scenario))
    except ValueError:
        pass  # do nothing if no base scenario is found

    costs = []  # total costs by type and scenario
    esums = []  # sum of energy produced by scenario

    # READ

    for rf in result_files:
        with pd.ExcelFile(rf) as xls:
            cost = xls.parse('Costs', index_col=[0])
            esum = xls.parse('Commodity sums')

            # repair broken MultiIndex in the first column
            esum.reset_index(inplace=True)
            esum.fillna(method='ffill', inplace=True)
            esum.set_index(['level_0', 'level_1'], inplace=True)

            costs.append(cost)

            # extract sites and commodities from scenario
            sitcom = [value.split('.') for value
                      in esum.columns.get_level_values(0)]
            coms = set([com for sit, com in sitcom])
            com_sums = pd.DataFrame()
            # get site.commodity names
            sit_com = esum.columns.get_level_values(0)
            # sum each commodity (e.g. Elec, CO2)
            for com in coms:
                com_sum = pd.DataFrame(esum.loc[:, sit_com.str.contains(com)]
                                       .sum(axis=1), columns=[com])
                com_sums = pd.concat([com_sums, com_sum], axis=1)
            esums.append(com_sums)

    # merge everything into one DataFrame each
    costs = pd.concat(costs, axis=1, keys=scenario_names)
    esums = pd.concat(esums, axis=1, keys=scenario_names)

    # ANALYSE

    # drop redundant 'costs' column label
    # make index name nicer for plot
    # sort/transpose frame
    # convert USD/a to 1e9 USD/a
    costs.columns = costs.columns.droplevel(1)
    costs.index.name = 'Cost type'
    costs = costs.sort_index().transpose()
    costs = costs / 1e9
    spent = costs.loc[:, costs.sum() > 0]
    earnt = costs.loc[:, costs.sum() < 0]

    # extract created
    # per commodity (e.g. 'Elec', 'CO2', 'Heat'...)
    # make index name 'Commodity' nicer for plot
    # drop all unused commodities and sort/transpose
    # convert kWh to MWh
    esums = esums.loc['Created']
    esums.index.name = 'Commodity'
    used_commodities = (esums.sum(axis=1) > 0)
    esums = esums[used_commodities].sort_index().transpose()
    esums = esums / 1e3

    # PLOT

    fig = plt.figure(figsize=(20, 8))
    gs = gridspec.GridSpec(1, 2, width_ratios=[2, 3])

    ax0 = plt.subplot(gs[0])
    spent_colors = [MvsoModel.to_color(ct) for ct in spent.columns]
    bp0 = spent.plot(ax=ax0, kind='barh', stacked=True, color=spent_colors,
                     linewidth=0)
    if not earnt.empty:
        earnt_colors = [MvsoModel.to_color(ct) for ct in earnt.columns]
        bp0a = earnt.plot(ax=ax0, kind='barh', stacked=True,
                          color=earnt_colors, linewidth=0)

    ax1 = plt.subplot(gs[1])
    esums_colors = [MvsoModel.to_color(commodity) for commodity in esums.columns]
    bp1 = esums.plot(ax=ax1, kind='barh', stacked=True, color=esums_colors,
                     linewidth=0, width=.5)

    # remove scenario names from second plot
    group_hbar_plots(ax1, len(coms))
    ax1.set_yticklabels(esums.index.get_level_values(1))

    # make bar plot edges lighter
    for bp in [bp0, bp1]:
        for patch in bp.patches:
            patch.set_edgecolor(MvsoModel.to_color('Decoration'))

    # set limits and ticks for both axes
    for ax in [ax0, ax1]:
        plt.setp(list(ax.spines.values()), color=MvsoModel.to_color('Grid'))
        ax.yaxis.grid(False)
        ax.xaxis.grid(True, 'major', color=MvsoModel.to_color('Grid'),
                      linestyle='-')
        ax.xaxis.set_ticks_position('none')
        ax.yaxis.set_ticks_position('none')

        # group 1,000,000 with commas
        group_thousands = tkr.FuncFormatter(lambda x,
                                            pos: '{:0,d}'.format(int(x)))
        ax.xaxis.set_major_formatter(group_thousands)

        # legend
        lg = ax.legend(frameon=False, loc='upper center',
                       ncol=4,
                       bbox_to_anchor=(0.5, 1.11))
        plt.setp(lg.get_patches(), edgecolor=MvsoModel.to_color('Decoration'),
                 linewidth=0)

    ax0.set_xlabel('Total costs (million USD/a)')
    if 'CO2' in coms:
        ax1.set_xlabel('Total energy produced (MWh)\n Emitted CO2 (kt)')
    else:
        ax1.set_xlabel('Total energy produced (MWh)')

    for ext in ['png', 'pdf']:
        fig.savefig('{}.{}'.format(output_filename, ext),
                    bbox_inches='tight')

    # REPORT
    with pd.ExcelWriter('{}.{}'.format(output_filename, 'xlsx')) as writer:
        costs.to_excel(writer, 'Costs')
        esums.to_excel(writer, 'Energy sums')

if __name__ == '__main__':

    directories = sys.argv[1:]
    if not directories:
        # get the directory of the supposedly last run
        # and retrieve (glob) a list of all result spreadsheets from there
        directories = [get_most_recent_entry('result')]

    for directory in directories:
        result_files = glob_result_files(directory)

        # specify comparison result filename
        # and run the comparison function
        comp_filename = os.path.join(directory, 'comparison')
        compare_scenarios(list(reversed(result_files)), comp_filename)

import os
import pandas as pd
import pyomo.environ
import shutil
import MvsoModel
from datetime import datetime
from pyomo.opt.base import SolverFactory


# SCENARIOS
def scenario_base(data):
    # do nothing    
    return data


def scenario_Node_2_process_caps(data):
    # change maximum installable capacity
    pro = data['process']
    pro.loc[('Node_2', 'Gas plant'), 'cap-up'] *= 0.5
    pro.loc[('Node_2', 'Biomass plant'), 'cap-up'] *= 0.25
    return data


def prepare_result_directory(result_name):
    """ create a time stamped directory within the result folder """
    # timestamp for result directory
    now = datetime.now().strftime('%Y%m%dT%H%M')

    # create result directory if not existent
    result_dir = os.path.join('result', '{}-{}'.format(result_name, now))
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)

    return result_dir


def setup_solver(optim, logfile='solver.log'):
    """ """
    if optim.name == 'gurobi':
        # reference with list of option names
        # http://www.gurobi.com/documentation/5.6/reference-manual/parameters
        optim.set_options("logfile={}".format(logfile))
        # optim.set_options("timelimit=7200")  # seconds
        # optim.set_options("mipgap=5e-4")  # default = 1e-4
    elif optim.name == 'glpk':
        # reference with list of options
        # execute 'glpsol --help'
        optim.set_options("log={}".format(logfile))
        # optim.set_options("tmlim=7200")  # seconds
        # optim.set_options("mipgap=.0005")
    else:
        print("Warning from setup_solver: no options set for solver "
              "'{}'!".format(optim.name))
    return optim


def run_scenario(input_file, timesteps, scenario, result_dir,
                 plot_tuples=None,  plot_sites_name=None, plot_periods=None,
                 report_tuples=None, report_sites_name=None):
    """ run an MvsoModel model for given input, time steps and scenario

    Args:
        input_file: filename to an Excel spreadsheet for MvsoModel.read_excel
        timesteps: a list of timesteps, e.g. range(0,8761)
        scenario: a scenario function that modifies the input data dict
        result_dir: directory name for result spreadsheet and plots
        plot_tuples: (optional) list of plot tuples (c.f. MvsoModel.result_figures)
        plot_sites_name: (optional) dict of names for sites in plot_tuples
        plot_periods: (optional) dict of plot periods(c.f. MvsoModel.result_figures)
        report_tuples: (optional) list of (sit, com) tuples (c.f. MvsoModel.report)
        report_sites_name: (optional) dict of names for sites in report_tuples

    Returns:
        the MvsoModel model instance
    """

    # scenario name, read and modify data for scenario
    sce = scenario.__name__
    data = MvsoModel.read_excel(input_file)
    data = scenario(data)
    MvsoModel.validate_input(data)

    # create model
    prob = MvsoModel.create_model(data, timesteps)

    # refresh time stamp string and create filename for logfile
    now = prob.created
    log_filename = os.path.join(result_dir, '{}.log').format(sce)

    # solve model and read results
    optim = SolverFactory('glpk')  # cplex, glpk, gurobi, ...
    optim = setup_solver(optim, logfile=log_filename)
    result = optim.solve(prob, tee=True)

    # save problem solution (and input data) to HDF5 file
    MvsoModel.save(prob, os.path.join(result_dir, '{}.h5'.format(sce)))

    # write report to spreadsheet
    MvsoModel.report(
        prob,
        os.path.join(result_dir, '{}.xlsx').format(sce),
        report_tuples=report_tuples,
        report_sites_name=report_sites_name)

    # result plots
    MvsoModel.result_figures(
        prob,
        os.path.join(result_dir, '{}'.format(sce)),
        plot_title_prefix=sce.replace('_', ' '),
        plot_tuples=plot_tuples,
        plot_sites_name=plot_sites_name,
        periods=plot_periods,
        figure_size=(24, 9))
    return prob

if __name__ == '__main__':
    input_file = 'macerich.xlsx'
    result_name = os.path.splitext(input_file)[0]  # cut away file extension
    result_dir = prepare_result_directory(result_name)  # name + time stamp

    # copy input file to result directory
    shutil.copyfile(input_file, os.path.join(result_dir, input_file))
    # copy runme.py to result directory
    shutil.copy(__file__, result_dir)

    # simulation timesteps
    (offset, length) = (0, 192)  # time step selection
    timesteps = range(offset, offset+length+1)

    # plotting commodities/sites
    plot_tuples = [
        ('Node_2', 'Elec'),
        ('Node_1', 'Elec'),
        (['Node_2', 'Node_1'], 'Elec')]

    # optional: define names for sites in plot_tuples
    plot_sites_name = {('Node_2', 'Node_1'): 'All'}

    # detailed reporting commodity/sites
    report_tuples = [
        ('Node_2', 'Elec'), ('Node_1', 'Elec'),
        ('Node_2', 'CO2'), ('Node_1', 'CO2')]

    # optional: define names for sites in report_tuples
    report_sites_name = {'Node_2': 'Greenland'}

    # plotting timesteps
    plot_periods = {
        'all': timesteps[1:]
    }

    # add or change plot colors
    my_colors = {
        'Node_1': (230, 200, 200),
        'Node_2': (200, 200, 230)}
    for country, color in my_colors.items():
        MvsoModel.COLORS[country] = color

    # select scenarios to be run
    scenarios = [
        scenario_base,
        scenario_Node_2_process_caps]

    for scenario in scenarios:
        prob = run_scenario(input_file, timesteps, scenario, result_dir,
                            plot_tuples=plot_tuples,
                            plot_sites_name=plot_sites_name,
                            plot_periods=plot_periods,
                            report_tuples=report_tuples,
                            report_sites_name=report_sites_name)

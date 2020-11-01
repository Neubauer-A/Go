#!/usr/local/bin/python
from gostuff.agents.predict import load_prediction_agent
from gostuff.agents import termination
from gostuff.gtp import GTPFrontend
from argparse import ArgumentParser
import h5py

parser = ArgumentParser()
parser.add_argument('--model', type=str, required=True)
args = parser.parse_args()

model_file = h5py.File(args.model, 'r')
agent = load_prediction_agent(model_file)
strategy = termination.get('resign')
termination_agent = termination.TerminationAgent(agent, strategy)

frontend = GTPFrontend(termination_agent)
frontend.run()

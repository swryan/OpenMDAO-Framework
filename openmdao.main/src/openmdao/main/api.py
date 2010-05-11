""" 
Pseudo package containing all of the main classes/objects in the 
openmdao.main API.

| *Basic OpenMDAO API*
|
|     Assembly
|     Component
|     Container
|     Dataflow
|     Driver
|     SimulationRoot
|     Workflow
|     set_as_top

| *Factories*
|
|     Factory
|     create
|     get_available_types

| *Exceptions*
|
|     ConstraintError

| *Data & File*
|
|         Case
|         ExprEvaluator
|         FileCaseIterator
|         FileMetadata
|         FileRef
|         ListCaseIterator
|         Expression
|         ExpressionList

| *Utilities*
|
|         convert_units
|         logger

| *Constants*
|
|         SAVE_CPICKLE
|         SAVE_LIBYAML
|         SAVE_PICKLE
|         SAVE_YAML

"""

from openmdao.util.log import logger, enable_console
from openmdao.main.expreval import ExprEvaluator

from openmdao.main.factory import Factory
from openmdao.main.factorymanager import create, get_available_types

from openmdao.main.container import Container, set_as_top
from openmdao.main.component import Component, SimulationRoot
from openmdao.main.assembly import Assembly
from openmdao.main.driver import Driver
from openmdao.main.workflow import Workflow
from openmdao.main.dataflow import Dataflow

from openmdao.main.exceptions import ConstraintError

from openmdao.main.expression import Expression, ExpressionList
from openmdao.main.filevar import FileMetadata, FileRef

from openmdao.main.case import Case, FileCaseIterator, ListCaseIterator

from openmdao.util.eggsaver import SAVE_YAML, SAVE_LIBYAML, \
                                   SAVE_PICKLE, SAVE_CPICKLE

from openmdao.units import convert_units

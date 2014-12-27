# -*- coding: utf-8 -*-


# OpenFisca -- A versatile microsimulation software
# By: OpenFisca Team <contact@openfisca.fr>
#
# Copyright (C) 2011, 2012, 2013, 2014 OpenFisca Team
# https://github.com/openfisca
#
# This file is part of OpenFisca.
#
# OpenFisca is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# OpenFisca is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""Parsers for formula-specific lib2to3-based abstract syntax trees"""


from __future__ import division

import collections
import inspect
import itertools
import lib2to3.pgen2.token
import lib2to3.pygram
import lib2to3.pytree
import textwrap

import numpy as np
from openfisca_core import conv


symbols = lib2to3.pygram.python_symbols  # Note: symbols is a module.
tokens = lib2to3.pgen2.token  # Note: tokens is a module.
type_symbol = lib2to3.pytree.type_repr  # Note: type_symbol is a function.


# Monkey patches to support utf-8 strings
lib2to3.pytree.Base.__str__ = lambda self: unicode(self).encode('utf-8')
lib2to3.pytree.Leaf.__unicode__ = lambda self: self.prefix.decode('utf-8') + (self.value.decode('utf-8')
    if isinstance(self.value, str)
    else unicode(self.value)
    )


class AbstractWrapper(object):
    _guess = None  # A wrapper that is the guessed type of this wrapper
    container = None  # The wrapper directly containing this wrapper
    node = None  # The lib2to3 node
    parser = None

    def __init__(self, container = None, guess = None, node = None, parser = None):
        if container is not None:
            assert isinstance(container, AbstractWrapper), "Invalid container {} for node:\n{}\n\n{}".format(container,
                repr(node), unicode(node).encode('utf-8'))
            self.container = container
        if guess is not None:
            assert isinstance(guess, AbstractWrapper), "Invalid guess {} for node:\n{}\n\n{}".format(guess, repr(node),
                unicode(node).encode('utf-8'))
            self._guess = guess
        if node is not None:
            assert isinstance(node, lib2to3.pytree.Base), "Invalid node:\n{}\n\n{}".format(repr(node),
                unicode(node).encode('utf-8'))
            self.node = node
        assert isinstance(parser, Parser), "Invalid parser {} for node:\n{}\n\n{}".format(parser, repr(node),
            unicode(node).encode('utf-8'))
        self.parser = parser

    @property
    def containing_class(self):
        container = self.container
        if container is None:
            return None
        return container.containing_class

    @property
    def containing_function(self):
        container = self.container
        if container is None:
            return None
        return container.containing_function

    @property
    def containing_module(self):
        container = self.container
        if container is None:
            return None
        return container.containing_module

    def guess_getter(self):
        return self._guess

    def guess_setter(self, guess):
        assert isinstance(guess, AbstractWrapper)
        self._guess = guess

    guess = property(guess_getter, guess_setter)


# class Array(AbstractWrapper):
#     column = None
#     data_type = None
#     entity_key_plural = None
#     is_argument = False
#     operation = None
#
#     def __init__(self, node, column = None, data_type = None, entity_key_plural = None, is_argument = False,
#             operation = None, parser = None):
#         super(Array, self).__init__(node, parser = parser)
#         if column is not None:
#             self.column = column
#             assert column.dtype == data_type, str((column.dtype, data_type))
#             assert column.entity_key_plural == entity_key_plural
#         if data_type is not None:
#             self.data_type = data_type
#         if entity_key_plural is not None:
#             self.entity_key_plural = entity_key_plural
#         if is_argument:
#             self.is_argument = True
#         if operation is not None:
#             self.operation = operation

#     @property
#     def guess(self):
#         return self._guess if self._guess is not None else self


# class ArrayLength(AbstractWrapper):
#     array = None
#
#     def __init__(self, node, array = None, parser = None):
#         super(ArrayLength, self).__init__(node, parser = parser)
#         if array is not None:
#             self.array = array

#     @property
#     def guess(self):
#         return self._guess if self._guess is not None else self.parser.Natural(parser = self.parser)


class Assignment(AbstractWrapper):
    operator = None
    variables = None

    def __init__(self, container = None, guess = None, node = None, operator = None, parser = None, variables = None):
        super(Assignment, self).__init__(container = container, guess = guess, node = node, parser = parser)
        assert isinstance(operator, basestring)
        self.operator = operator
        assert isinstance(variables, list)
        self.variables = variables

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.expr_stmt, "Expected a node of type {}. Got:\n{}\n\n{}".format(
            type_symbol(symbols.expr_stmt), repr(node), unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 3, "Unexpected length {} of children in assignment:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        left, operator, right = children
        assert operator.type in (tokens.EQUAL, tokens.MINEQUAL, tokens.PLUSEQUAL, tokens.STAREQUAL), \
            "Unexpected assignment operator:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
        variables = []
        if left.type == symbols.testlist_star_expr:
            assert right.type == symbols.testlist_star_expr
            left_children = left.children
            right_children = right.children
            assert len(left_children) == len(right_children), \
                "Unexpected length difference for left & right in assignment:\n{}\n\n{}".format(repr(node),
                    unicode(node).encode('utf-8'))
            child_index = 0
            while child_index < len(left_children):
                left_child = left_children[child_index]
                assert left_child.type == tokens.NAME
                assert operator.value == tokens.EQUAL
                right_child = right_children[child_index]
                value = parser.parse_value(right_child, container = container)
                variable = parser.Variable.parse(left_child, container = container, parser = parser, value = value)
                variables.append(variable)
                container.variable_by_name[variable.name] = variable

                child_index += 1
                if child_index >= len(left_children):
                    break
                assert left_children[child_index].type == tokens.COMMA
                child_index += 1
        elif left.type == symbols.power:
            TODO
            # self.left = parser.parse_power(left, container = container)
            # self.right = parser.parse_value(right, container = container)
        else:
            assert left.type == tokens.NAME, \
                "Unexpected assignment left operand:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            value = parser.parse_value(right, container = container)
            variable = parser.Variable.parse(left, container = container, parser = parser, value = value)
            variables.append(variable)
            container.variable_by_name[variable.name] = variable
        return cls(container = container, node = node, operator = operator.value, parser = parser,
            variables = variables)


class Attribute(AbstractWrapper):
    name = None
    subject = None

    def __init__(self, container = None, guess = None, name = None, node = None, parser = None, subject = None):
        super(Attribute, self).__init__(container = container, guess = guess, node = node, parser = parser)
        assert isinstance(name, basestring)
        self.name = name
        assert isinstance(subject, AbstractWrapper)
        self.subject = subject

        if self.guess is None:
            subject_guess = subject.guess
            if name == 'start':
                if isinstance(subject_guess, parser.Period):
                    self.guess = parser.Instant(parser = parser)

    @classmethod
    def parse(cls, subject, node, container = None, parser = None):
        assert node.type == symbols.trailer, "Unexpected attribute type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 2, "Unexpected length {} of children in power attribute:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        dot, attribute = children
        assert dot.type == tokens.DOT, "Unexpected dot type:\n{}\n\n{}".format(repr(dot), unicode(dot).encode('utf-8'))
        assert attribute.type == tokens.NAME, "Unexpected attribute type:\n{}\n\n{}".format(repr(attribute),
            unicode(attribute).encode('utf-8'))
        return cls(container = container, name = attribute.value, node = node, parser = parser, subject = subject)


class Call(AbstractWrapper):
    named_arguments = None
    positional_arguments = None
    subject = None

    def __init__(self, container = None, guess = None, named_arguments = None, node = None, parser = None,
            positional_arguments = None, subject = None):
        super(Call, self).__init__(container = container, guess = guess, node = node, parser = parser)
        if named_arguments is None:
            named_arguments = collections.OrderedDict()
        else:
            assert isinstance(named_arguments, collections.OrderedDict)
        self.named_arguments = named_arguments
        if positional_arguments is None:
            positional_arguments = []
        else:
            assert isinstance(positional_arguments, list)
        self.positional_arguments = positional_arguments
        assert isinstance(subject, AbstractWrapper)
        self.subject = subject

        if self.guess is None:
            if isinstance(subject, parser.Attribute):
                method_name = subject.name
                if method_name == 'offset':
                    method_subject_guess = subject.subject.guess
                    if isinstance(method_subject_guess, parser.Instant):
                        self.guess = parser.Instant(parser = parser)
                    elif isinstance(method_subject_guess, parser.Period):
                        self.guess = parser.Period(parser = parser)
            elif isinstance(subject, parser.Function):
                function_name = subject.name
                if function_name == 'date':
                    self.guess = parser.Date(parser = parser)

    @classmethod
    def parse(cls, subject, node, container = None, parser = None):
        if node.type == symbols.arglist:
            children = node.children
        else:
            children = [node]
        named_arguments = collections.OrderedDict()
        positional_arguments = []
        child_index = 0
        while child_index < len(children):
            argument = children[child_index]
            if argument.type == symbols.argument:
                # Named argument
                argument_children = argument.children
                assert len(argument_children) == 3, "Unexpected length {} of children in argument:\n{}\n\n{}".format(
                    len(argument_children), repr(argument), unicode(argument).encode('utf-8'))
                argument_name, equal, argument_value = argument_children
                assert argument_name.type == tokens.NAME, "Unexpected name type:\n{}\n\n{}".format(repr(argument_name),
                    unicode(argument_name).encode('utf-8'))
                assert equal.type == tokens.EQUAL, "Unexpected equal type:\n{}\n\n{}".format(repr(equal),
                    unicode(equal).encode('utf-8'))
                named_arguments[argument_name.value] = parser.parse_value(argument_value, container = container)
            else:
                # Positional argument
                positional_arguments.append(parser.parse_value(argument, container = container))
            child_index += 1
            if child_index >= len(children):
                break
            child = children[child_index]
            assert child.type == tokens.COMMA, "Unexpected comma type:\n{}\n\n{}".format(repr(child),
                unicode(child).encode('utf-8'))
            child_index += 1
        return cls(container = container, named_arguments = named_arguments, node = node, parser = parser,
            positional_arguments = positional_arguments, subject = subject)


class Class(AbstractWrapper):
    base_class_name = None
    name = None
    variable_by_name = None

    def __init__(self, base_class_name = None, container = None, name = None, node = None, parser = None,
            variable_by_name = None):
        super(Class, self).__init__(container = container, node = node, parser = parser)
        assert isinstance(base_class_name, basestring)
        self.base_class_name = base_class_name
        assert isinstance(name, basestring)
        self.name = name
        if variable_by_name is None:
            variable_by_name = collections.OrderedDict()
        else:
            assert isinstance(variable_by_name, collections.OrderedDict)
        self.variable_by_name = variable_by_name

    @property
    def containing_class(self):
        return self

    @classmethod
    def get_function_class(cls, parser = None):
        return parser.Function

    def get_variable(self, name, default = UnboundLocalError, parser = None):
        variable = self.variable_by_name.get(name, None)
        if variable is None:
            container = self.container
            if container is not None:
                return container.get_variable(name, default = default, parser = parser)
            # TODO: Handle class inheritance.
            if default is UnboundLocalError:
                raise KeyError("Undefined value for {}".format(name))
            variable = default
        return variable

    @property
    def guess(self):
        return self._guess if self._guess is not None else self

    @classmethod
    def parse(cls, node, container = None, parser = None):
        try:
            children = node.children
            assert len(children) == 7, len(children)
            assert children[0].type == tokens.NAME and children[0].value == 'class'
            assert children[1].type == tokens.NAME
            name = children[1].value
            assert children[2].type == tokens.LPAR and children[2].value == '('
            assert children[3].type == tokens.NAME
            base_class_name = children[3].value
            assert children[4].type == tokens.RPAR and children[4].value == ')'
            assert children[5].type == tokens.COLON and children[5].value == ':'

            variable_by_name = collections.OrderedDict()
            self = cls(base_class_name = base_class_name, container = container, name = name, node = node,
                parser = parser, variable_by_name = variable_by_name)

            suite = children[6]
            assert suite.type == symbols.suite
            suite_children = suite.children
            assert len(suite_children) > 2, len(suite_children)
            assert suite_children[0].type == tokens.NEWLINE and suite_children[0].value == '\n'
            assert suite_children[1].type == tokens.INDENT and suite_children[1].value == '    '
            for suite_child in itertools.islice(suite_children, 2, None):
                if suite_child.type == symbols.decorated:
                    decorator = parser.Decorator.parse(suite_child, container = self, parser = parser)
                    variable_by_name[decorator.decorated.name] = decorator
                elif suite_child.type == symbols.funcdef:
                    function = cls.get_function_class(parser = parser).parse(suite_child, container = self,
                        parser = parser)
                    variable_by_name[function.name] = function
                elif suite_child.type == symbols.simple_stmt:
                    assert len(suite_child.children) == 2, len(suite_child.children)
                    expression = suite_child.children[0]
                    assert expression.type in (symbols.expr_stmt, tokens.STRING), expression.type
                    assert suite_child.children[1].type == tokens.NEWLINE and suite_child.children[1].value == '\n'
                elif suite_child.type == tokens.DEDENT:
                    continue
                else:
                    assert False, "Unexpected statement in class definition:\n{}\n\n{}".format(repr(suite_child),
                        unicode(suite_child).encode('utf-8'))
            return self
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise


class ClassFileInput(AbstractWrapper):
    @classmethod
    def get_class_class(cls, parser = None):
        return parser.Class

    @classmethod
    def parse(cls, class_definition, parser = None):
        source_lines, line_number = inspect.getsourcelines(class_definition)
        source = textwrap.dedent(''.join(source_lines))
        node = parser.driver.parse_string(source)
        assert node.type == symbols.file_input, "Expected a node of type {}. Got:\n{}\n\n{}".format(
            type_symbol(symbols.file_input), repr(node), unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 2 and children[0].type == symbols.classdef and children[1].type == tokens.ENDMARKER, \
            "Unexpected node children in:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
        module = parser.Module(node, python = inspect.getmodule(class_definition), parser = parser)
        self = cls(parser = parser)
        class_definition_class = self.get_class_class(parser = parser)
        try:
            return class_definition_class.parse(children[0], container = module, parser = parser)
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise


# class Continue(AbstractWrapper):
#     pass


class Date(AbstractWrapper):
    @property
    def guess(self):
        return self._guess if self._guess is not None else self


# class DatedHolder(AbstractWrapper):
#     column = None
#     data_type = None
#     entity_key_plural = None
#     is_argument = False

#     def __init__(self, node, column = None, data_type = None, entity_key_plural = None, is_argument = False,
#             parser = None):
#         super(DatedHolder, self).__init__(node, parser = parser)
#         if column is not None:
#             self.column = column
#             assert column.dtype == data_type, str((column.dtype, data_type))
#             assert column.entity_key_plural == entity_key_plural
#         if data_type is not None:
#             self.data_type = data_type
#         if entity_key_plural is not None:
#             self.entity_key_plural = entity_key_plural
#         if is_argument:
#             self.is_argument = True

#     @property
#     def guess(self):
#         return self._guess if self._guess is not None else self


# class DateTime64(AbstractWrapper):
#     @property
#     def guess(self):
#         return self._guess if self._guess is not None else self


class Decorator(AbstractWrapper):
    decorated = None
    name = None
    subject = None  # The decorator

    def __init__(self, container = None, decorated = None, name = None, node = None, parser = None, subject = None):
        super(Decorator, self).__init__(container = container, node = node, parser = parser)
        assert isinstance(decorated, AbstractWrapper)
        self.decorated = decorated
        assert isinstance(name, basestring)
        self.name = name
        assert isinstance(subject, AbstractWrapper)
        self.subject = subject

    @classmethod
    def parse(cls, node, container = None, parser = None):
        try:
            children = node.children
            assert len(children) == 2, len(children)

            decorator = children[0]
            assert decorator.type == symbols.decorator
            decorator_children = decorator.children
            assert len(decorator_children) == 6, len(decorator_children)
            assert decorator_children[0].type == tokens.AT and decorator_children[0].value == '@'
            subject = parser.Variable.parse(decorator_children[1], container = container, parser = parser)
            name = decorator_children[1].value
            assert decorator_children[2].type == tokens.LPAR and decorator_children[2].value == '('
            subject = parser.Call.parse(subject, decorator_children[3], container = container, parser = parser)
            assert decorator_children[4].type == tokens.RPAR and decorator_children[4].value == ')'
            assert decorator_children[5].type == tokens.NEWLINE and decorator_children[5].value == '\n'
            subject = subject

            decorated = children[1]
            assert decorated.type == symbols.funcdef
            decorated = container.get_function_class(parser = parser).parse(decorated, container = container,
                parser = parser)

            return cls(container = container, decorated = decorated, name = name, node = node, parser = parser,
                subject = subject)
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise


class Enum(AbstractWrapper):
    value = None

    def __init__(self, container = None, node = None, parser = None, value = None):
        super(Enum, self).__init__(container = container, node = node, parser = parser)
        if value is not None:
            self.value = value

    @property
    def guess(self):
        return self._guess if self._guess is not None else self


# class Entity(AbstractWrapper):
#     @property
#     def guess(self):
#         return self._guess if self._guess is not None else self


# class EntityToEntity(AbstractWrapper):
#     keyword_arguments = None
#     method_name = None
#     named_arguments = None
#     positional_arguments = None
#     star_arguments = None

#     def __init__(self, node, keyword_arguments = None, method_name = None, named_arguments = None,
#             positional_arguments = None, star_arguments = None, parser = None):
#         super(EntityToEntity, self).__init__(node, parser = parser)
#         if keyword_arguments is not None:
#             self.keyword_arguments = keyword_arguments
#         if method_name is not None:
#             self.method_name = method_name
#         if named_arguments is not None:
#             self.named_arguments = named_arguments
#         if positional_arguments is not None:
#             self.positional_arguments = positional_arguments
#         if star_arguments is not None:
#             self.star_arguments = star_arguments


# class For(AbstractWrapper):
#     def __init__(self, node, container = None, parser = None):
#         super(For, self).__init__(node, container = container, parser = parser)

#         # TODO: Parse and store attributes.


class Function(AbstractWrapper):
    body = None
    name = None
    named_parameters = None  # Dictionary of parameter name => default value
    positional_parameters = None  # List of parameters names
    returns = None  # List of Return wrappers present in function
    variable_by_name = None

    def __init__(self, body = None, container = None, name = None, named_parameters = None, node = None, parser = None,
            positional_parameters = None, returns = None, variable_by_name = None):
        super(Function, self).__init__(container = container, node = node, parser = parser)
        if body is None:
            body = []
        else:
            assert isinstance(body, list)
        self.body = body
        assert isinstance(name, basestring)
        self.name = name
        if named_parameters is None:
            named_parameters = collections.OrderedDict()
        else:
            assert isinstance(named_parameters, collections.OrderedDict)
        self.named_parameters = named_parameters
        if positional_parameters is None:
            positional_parameters = []
        else:
            assert isinstance(positional_parameters, list)
        self.positional_parameters = positional_parameters
        if returns is None:
            returns = []
        else:
            assert isinstance(returns, list)
        self.returns = returns
        if variable_by_name is None:
            variable_by_name = collections.OrderedDict()
        else:
            assert isinstance(variable_by_name, collections.OrderedDict)
        self.variable_by_name = variable_by_name

    @classmethod
    def parse(cls, node, container = None, parser = None):
        try:
            children = node.children
            assert len(children) == 5
            assert children[0].type == tokens.NAME and children[0].value == 'def'
            assert children[1].type == tokens.NAME  # Function name
            name = children[1].value

            self = cls(container = container, name = name, node = node, parser = parser)
            self.parse_parameters()

            suite = children[4]
            assert suite.type == symbols.suite
            suite_children = suite.children
            assert suite_children[0].type == tokens.NEWLINE and suite_children[0].value == '\n'
            assert suite_children[1].type == tokens.INDENT
            for suite_child in itertools.islice(suite_children, 2, None):
                if suite_child.type == symbols.for_stmt:
                    for_wrapper = parser.For.parse(suite_child, container = self, parser = parser)
                    self.body.append(for_wrapper)
                elif suite_child.type == symbols.funcdef:
                    function = parser.Function.parse(suite_child, container = self, parser = parser)
                    self.body.append(function)
                    self.variable_by_name[function.name] = function
                elif suite_child.type == symbols.if_stmt:
                    if_wrapper = parser.If.parse(suite_child, container = self, parser = parser)
                    self.body.append(if_wrapper)
                elif suite_child.type == symbols.simple_stmt:
                    assert len(suite_child.children) == 2, \
                        "Unexpected length {} for simple statement in function definition:\n{}\n\n{}".format(
                            len(suite_child.children), repr(suite_child), unicode(suite_child).encode('utf-8'))
                    statement = suite_child.children[0]
                    if statement.type == symbols.expr_stmt:
                        assignment = parser.Assignment.parse(statement, container = self, parser = parser)
                        self.body.append(assignment)
                    elif statement.type == symbols.return_stmt:
                        return_wrapper = parser.Return.parse(statement, container = self, parser = parser)
                        self.body.append(return_wrapper)
                    else:
                        assert statement.type in (symbols.power, tokens.STRING), type_symbol(statement.type)
                    assert suite_child.children[1].type == tokens.NEWLINE and suite_child.children[1].value == '\n'
                elif suite_child.type == tokens.DEDENT:
                    continue
                else:
                    assert False, "Unexpected statement in function definition:\n{}\n\n{}".format(repr(suite_child),
                        unicode(suite_child).encode('utf-8'))
            return self
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise

    @property
    def containing_function(self):
        return self

    def get_variable(self, name, default = UnboundLocalError, parser = None):
        variable = self.variable_by_name.get(name, None)
        if variable is None:
            container = self.container
            if container is not None:
                return container.get_variable(name, default = default, parser = parser)
            if default is UnboundLocalError:
                raise KeyError("Undefined value for {}".format(name))
            variable = default
        return variable

    @property
    def guess(self):
        return self._guess if self._guess is not None else self

    def parse_parameters(self):
        parser = self.parser
        children = self.node.children
        assert len(children) == 5

        parameters = children[2]
        assert parameters.type == symbols.parameters
        parameters_children = parameters.children
        assert len(parameters_children) == 3
        assert parameters_children[0].type == tokens.LPAR and parameters_children[0].value == '('

        if parameters_children[1].type == tokens.NAME:
            # Single positional parameter
            typedargslist = None
            typedargslist_children = [parameters_children[1]]
        else:
            typedargslist = parameters_children[1]
            assert typedargslist.type == symbols.typedargslist
            typedargslist_children = typedargslist.children

        typedargslist_child_index = 0
        while typedargslist_child_index < len(typedargslist_children):
            typedargslist_child = typedargslist_children[typedargslist_child_index]
            assert typedargslist_child.type == tokens.NAME
            parameter_name = typedargslist_child.value
            typedargslist_child_index += 1
            if typedargslist_child_index >= len(typedargslist_children):
                # Last positional parameter
                self.positional_parameters.append(parameter_name)
                self.variable_by_name[parameter_name] = parser.Variable(container = self, name = parameter_name,
                    parser = parser)
                break
            typedargslist_child = typedargslist_children[typedargslist_child_index]
            if typedargslist_child.type == tokens.COMMA:
                # Positional parameter
                self.positional_parameters.append(parameter_name)
                self.variable_by_name[parameter_name] = parser.Variable(container = self, name = parameter_name,
                    parser = parser)
                typedargslist_child_index += 1
            elif typedargslist_child.type == tokens.EQUAL:
                # Named parameter
                typedargslist_child_index += 1
                typedargslist_child = typedargslist_children[typedargslist_child_index]
                self.named_parameters[parameter_name] = parser.parse_value(typedargslist_child, container = self)
                self.variable_by_name[parameter_name] = parser.Variable(container = self, Name = parameter_name,
                    parser = parser)
                typedargslist_child_index += 1
                if typedargslist_child_index >= len(typedargslist_children):
                    break
                typedargslist_child = typedargslist_children[typedargslist_child_index]
                assert typedargslist_child.type == tokens.COMMA
                typedargslist_child_index += 1

        assert parameters_children[2].type == tokens.RPAR and parameters_children[2].value == ')'

        assert children[3].type == tokens.COLON and children[3].value == ':'


# class FunctionCall(AbstractWrapper):
#     definition = None
#     variable_by_name = None

#     def __init__(self, node, definition = None, parser = None):
#         super(FunctionCall, self).__init__(node, parser = parser)
#         assert isinstance(definition, Function)
#         self.definition = definition
#         self.variable_by_name = collections.OrderedDict()

#     def get_variable(self, name, default = UnboundLocalError, parser = None):
#         variable = self.variable_by_name.get(name, None)
#         if variable is None:
#             container = self.definition.container
#             if container is not None:
#                 return container.get_variable(name, default = default, parser = parser)
#             if default is UnboundLocalError:
#                 raise KeyError("Undefined value for {}".format(name))
#             variable = default
#         return variable


# class FunctionFileInput(AbstractWrapper):
#     @classmethod
#     def get_function_class(cls, parser = None):
#         return parser.Function

#     @classmethod
#     def parse(cls, function, parser = None):
#         source_lines, line_number = inspect.getsourcelines(function)
#         source = textwrap.dedent(''.join(source_lines))
#         # print source
#         node = parser.driver.parse_string(source)
#         assert node.type == symbols.file_input, "Expected a node of type {}. Got:\n{}\n\n{}".format(
#             type_symbol(symbols.file_input), repr(node), unicode(node).encode('utf-8'))
#         children = node.children
#         assert len(children) == 2 and children[0].type == symbols.funcdef and children[1].type == tokens.ENDMARKER, \
#             "Unexpected node children in:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
#         module = parser.Module(node, python = inspect.getmodule(function), parser = parser)
#         self = cls(parser = parser)
#         function_class = cls.get_function_class(parser = parser)
#         try:
#             return function_class(children[0], container = module, parser = parser)
#         except:
#             if node is not None:
#                 print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
#             raise


# class Holder(AbstractWrapper):
#     formula = None

#     def __init__(self, node, formula = None, parser = None):
#         super(Holder, self).__init__(node, parser = parser)
#         if formula is not None:
#             self.formula = formula

#     @property
#     def guess(self):
#         return self._guess if self._guess is not None else self


# class If(AbstractWrapper):
#     def __init__(self, node, container = None, parser = None):
#         super(If, self).__init__(node, container = container, parser = parser)

#         # TODO: Parse and store attributes.


class Instant(AbstractWrapper):
    @property
    def guess(self):
        return self._guess if self._guess is not None else self


class Key(AbstractWrapper):
    subject = None
    value = None  # Value of the key

    def __init__(self, container = None, node = None, parser = None, subject = None, value = None):
        super(Key, self).__init__(container = container, node = node, parser = parser)
        assert isinstance(subject, AbstractWrapper)
        self.subject = subject
        assert isinstance(value, (basestring, int))
        self.value = value

    @classmethod
    def parse(cls, subject, node, container = None, parser = None):
        assert node.type == symbols.trailer, "Unexpected key type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 3, "Unexpected length {} of children in power key:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        left_bracket, key, right_bracket = children
        assert left_bracket.type == tokens.LSQB, "Unexpected left bracket type:\n{}\n\n{}".format(repr(left_bracket),
            unicode(left_bracket).encode('utf-8'))
        value = parser.parse_value(key, container = container)
        assert right_bracket.type == tokens.RSQB, "Unexpected right bracket type:\n{}\n\n{}".format(repr(right_bracket),
            unicode(right_bracket).encode('utf-8'))
        return cls(container = container, node = node, parser = parser, subject = subject, value = value)


# class Lambda(Function):
#     pass


class LawNode(AbstractWrapper):
    is_reference = True
    name = None
    parent = None  # Parent LawNode instance

    def __init__(self, is_reference = False, name = None, parent = None, parser = None):
        super(LawNode, self).__init__(parser = parser)
        if not is_reference:
            self.is_reference = False
        assert (parent is None) == (name is None), str((name, parent))
        if name is not None:
            self.name = name
        if parent is not None:
            assert isinstance(parent, LawNode)
            self.parent = parent

    @property
    def guess(self):
        return self._guess if self._guess is not None else self

    def iter_names(self):
        parent = self.parent
        if parent is not None:
            for ancestor_name in parent.iter_names():
                yield ancestor_name
        name = self.name
        if name is not None:
            yield name

    @property
    def path(self):
        return '.'.join(self.iter_names())


class Logger(AbstractWrapper):
    @property
    def guess(self):
        return self._guess if self._guess is not None else self


# class Math(AbstractWrapper):
#     pass


class Module(AbstractWrapper):
    python = None
    variable_by_name = None

    def __init__(self, node, python = None, parser = None):
        super(Module, self).__init__(node = node, parser = parser)
        if python is not None:
            # Python module
            self.python = python
        self.variable_by_name = collections.OrderedDict(sorted(dict(
            CAT = parser.Variable(container = self, name = u'CAT', parser = parser,
                value = parser.Enum(parser = parser, value = None)),  # TODO
            CHEF = parser.Variable(container = self, name = u'CHEF', parser = parser,
                value = parser.Number(parser = parser, value = 0)),
            CONJ = parser.Variable(container = self, name = u'CONJ', parser = parser,
                value = parser.Number(parser = parser, value = 1)),
            CREF = parser.Variable(container = self, name = u'CREF', parser = parser,
                value = parser.Number(parser = parser, value = 1)),
            date = parser.Function(container = self, name = u'date', parser = parser),
            # ENFS = parser.Variable(container = self, name = u'ENFS', parser = parser,
            #     value = parser.UniformList(parser = parser, value = parser.Number(parser = parser, value = x))),
            int16 = parser.Variable(container = self, name = u'int16', parser = parser,
                value = parser.Type(parser = parser, value = np.int16)),
            int32 = parser.Variable(container = self, name = u'int32', parser = parser,
                value = parser.Type(parser = parser, value = np.int32)),
            law = parser.Variable(container = self, name = u'law', parser = parser,
                value = parser.LawNode(parser = parser)),
            log = parser.Variable(container = self, name = u'log', parser = parser,
                value = parser.Logger(parser = parser)),
            max_ = parser.Function(container = self, name = u'max_', parser = parser),
            min_ = parser.Function(container = self, name = u'min_', parser = parser),
            PAC1 = parser.Variable(container = self, name = u'PAC1', parser = parser,
                value = parser.Number(parser = parser, value = 2)),
            PAC2 = parser.Variable(container = self, name = u'PAC2', parser = parser,
                value = parser.Number(parser = parser, value = 3)),
            PAC3 = parser.Variable(container = self, name = u'PAC3', parser = parser,
                value = parser.Number(parser = parser, value = 4)),
            PART = parser.Variable(container = self, name = u'PART', parser = parser,
                value = parser.Number(parser = parser, value = 1)),
            PREF = parser.Variable(container = self, name = u'PREF', parser = parser,
                value = parser.Number(parser = parser, value = 0)),
            TAUX_DE_PRIME = parser.Variable(container = self, name = u'TAUX_DE_PRIME', parser = parser,
                value = parser.Number(parser = parser, value = 1 / 4)),
            VOUS = parser.Variable(container = self, name = u'VOUS', parser = parser,
                value = parser.Number(parser = parser, value = 0)),
            ).iteritems()))

    @property
    def containing_module(self):
        return self

    def get_variable(self, name, default = UnboundLocalError, parser = None):
        variable = self.variable_by_name.get(name, None)
        if variable is None:
            value = getattr(self.python, name, UnboundLocalError)
            if value is UnboundLocalError:
                if default is UnboundLocalError:
                    raise KeyError("Undefined value for {}".format(name))
                return default
            if not inspect.isfunction(value):
                # TODO?
                if default is UnboundLocalError:
                    raise KeyError("Undefined value for {}".format(name))
                return default
            function = conv.check(parser.FunctionFileInput.parse)(value, parser)
            self.variable_by_name[name] = variable = parser.Variable(container = self, name = name,
                parser = parser, value = function)
        return variable

    @property
    def guess(self):
        return self._guess if self._guess is not None else self


class Number(AbstractWrapper):
    value = None  # Number value, as a string

    def __init__(self, container = None, node = None, parser = None, value = None):
        super(Number, self).__init__(container = container, node = node, parser = parser)
        assert isinstance(value, (int, float, str)), "Unexpected value for number: {} of type {}".format(value,
            type(value))
        self.value = str(value)

    @property
    def guess(self):
        return self._guess if self._guess is not None else self

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == tokens.NUMBER, "Unexpected number type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        return cls(container = container, node = node, parser = parser, value = node.value)


class Period(AbstractWrapper):
    @property
    def guess(self):
        return self._guess if self._guess is not None else self


class Return(AbstractWrapper):
    value = None

    def __init__(self, container = None, guess = None, node = None, parser = None, value = None):
        super(Return, self).__init__(container = container, guess = guess, node = node, parser = parser)
        assert isinstance(value, AbstractWrapper)
        self.value = value

        containing_function = self.containing_function
        containing_function.returns.append(self)

    @property
    def guess(self):
        return self._guess \
            if self._guess is not None\
            else self.value.guess if self.value is not None else None

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.return_stmt, "Unexpected return type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 2, len(children)
        assert children[0].type == tokens.NAME and children[0].value == 'return'
        value = parser.parse_value(children[1], container = container)

        return cls(container = container, node = node, parser = parser, value = value)


class Simulation(AbstractWrapper):
    pass


class String(AbstractWrapper):
    value = None  # String value, as a string

    def __init__(self, container = None, node = None, parser = None, value = None):
        super(String, self).__init__(container = container, node = node, parser = parser)
        assert isinstance(value, basestring), "Unexpected value for string: {} of type {}".format(value,
            type(value))
        if isinstance(value, str):
            value = value.decode('utf-8')
        if value.startswith(u'u'):
            value = value[1:]
        for delimiter in (u'"', u"'", u'"""', u"'''"):
            if value.startswith(delimiter) and value.endswith(delimiter):
                value = value[len(delimiter):-len(delimiter)]
                break
        else:
            assert False, "Unknow delimiters for: {}".format(value)
        self.value = value

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == tokens.STRING, "Unexpected string type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        return cls(container = container, node = node, parser = parser, value = node.value)


# class Structure(AbstractWrapper):
#     items = None

#     def __init__(self, node, items = None, parser = None):
#         super(Structure, self).__init__(node, parser = parser)
#         self.items = items

#     @property
#     def guess(self):
#         return self._guess if self._guess is not None else self


# class TaxScalesTree(AbstractWrapper):
#     pass

#     @property
#     def guess(self):
#         return self._guess if self._guess is not None else self


class Tuple(AbstractWrapper):
    value = None  # Tuple value, as a tuple

    def __init__(self, container = None, guess = None, node = None, parser = None, value = None):
        super(Tuple, self).__init__(container = container, guess = guess, node = node, parser = parser)
        assert isinstance(value, tuple), "Unexpected value for tuple: {} of type {}".format(value,
            type(value))
        self.value = value

    @property
    def guess(self):
        return self._guess if self._guess is not None else self

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.testlist, "Unexpected tuple type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))

        items = []
        item_index = 0
        while item_index < len(items):
            item = items[item_index]
            items.append(parser.parse_value(item, container = container))
            item_index += 1
            if item_index >= len(items):
                break
            comma = items[item_index]
            assert comma.type == tokens.COMMA, "Unexpected comma type:\n{}\n\n{}".format(repr(comma),
                unicode(comma).encode('utf-8'))
            item_index += 1

        return cls(container = container, node = node, parser = parser, value = tuple(items))


class Type(AbstractWrapper):
    value = None

    def __init__(self, container = None, node = None, parser = None, value = None):
        super(Type, self).__init__(container = container, node = node, parser = parser)
        if value is not None:
            self.value = value

    @property
    def guess(self):
        return self._guess if self._guess is not None else self


# class UniformDictionary(AbstractWrapper):
#     key = None
#     value = None

#     def __init__(self, node, key = None, value = None, parser = None):
#         super(UniformDictionary, self).__init__(node, parser = parser)
#         if key is not None:
#             self.key = key
#         if value is not None:
#             self.value = value

#     @property
#     def guess(self):
#         return self._guess if self._guess is not None else self


# class UniformIterator(AbstractWrapper):
#     item = None

#     def __init__(self, node, item = None, parser = None):
#         super(UniformIterator, self).__init__(node, parser = parser)
#         if item is not None:
#             self.item = item

#     @property
#     def guess(self):
#         return self._guess if self._guess is not None else self


# class UniformList(AbstractWrapper):
#     item = None

#     def __init__(self, node, item = None, parser = None):
#         super(UniformList, self).__init__(node, parser = parser)
#         if item is not None:
#             self.item = item

#     @property
#     def guess(self):
#         return self._guess if self._guess is not None else self


class Variable(AbstractWrapper):
    name = None
    value = None  # A value wrapper

    def __init__(self, container = None, guess = None, name = None, node = None, parser = None, value = None):
        super(Variable, self).__init__(container = container, guess = guess, node = node, parser = parser)
        assert isinstance(name, basestring)
        self.name = name
        if value is not None:
            assert isinstance(value, AbstractWrapper)
            self.value = value

    @property
    def guess(self):
        return self._guess \
            if self._guess is not None\
            else self.value.guess if self.value is not None else None

    @classmethod
    def parse(cls, node, container = None, parser = None, value = None):
        assert node.type == tokens.NAME, "Unexpected variable type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        return cls(container = container, name = node.value, node = node, parser = parser, value = value)


# Formula-specific classes


class Formula(AbstractWrapper):
    pass


class FormulaClass(Class):
    @classmethod
    def get_function_class(cls, parser = None):
        return parser.FormulaFunction


class FormulaClassFileInput(ClassFileInput):
    # Caution: This is not the whole module, but only a dummy "module" containing only the formula.
    @classmethod
    def get_class_class(cls, parser = None):
        return parser.FormulaClass


class FormulaFunction(Function):
    def parse_parameters(self):
        super(FormulaFunction, self).parse_parameters()
        parser = self.parser
        assert self.positional_parameters == ['self', 'simulation', 'period'], self.positional_arguments
        assert not self.named_parameters, self.named_arguments
        simulation_variable = self.variable_by_name['simulation']
        assert simulation_variable.value is None, simulation_variable.value
        simulation_variable.value = parser.Simulation(parser = self.parser)
        period_variable = self.variable_by_name['period']
        assert period_variable.value is None, period_variable.value
        period_variable.value = parser.Period(parser = self.parser)


# class FormulaFunctionFileInput(FunctionFileInput):
#     # Caution: This is not the whole module, but only a dummy "module" containing only the formula.
#     @classmethod
#     def get_function_class(cls, parser = None):
#         return parser.FormulaFunction


# Default Parser


class Parser(conv.State):
    column = None  # Formula column
    # Array = Array
    # ArrayLength = ArrayLength
    Assignment = Assignment
    Attribute = Attribute
    Call = Call
    Class = Class
    ClassFileInput = ClassFileInput
    # Continue = Continue
    Date = Date
    # DateTime64 = DateTime64
    # DatedHolder = DatedHolder
    Decorator = Decorator
    driver = None
    # Entity = Entity
    # EntityToEntity = EntityToEntity
    Enum = Enum
    # For = For
    Formula = Formula
    FormulaClass = FormulaClass
    FormulaClassFileInput = FormulaClassFileInput
    FormulaFunction = FormulaFunction
    # FormulaFunctionFileInput = FormulaFunctionFileInput
    Function = Function
    # FunctionCall = FunctionCall
    # FunctionFileInput = FunctionFileInput
    # Holder = Holder
    # If = If
    Instant = Instant
    Key = Key
    # Lambda = Lambda
    LawNode = LawNode
    Logger = Logger
    # Math = Math
    Module = Module
    Number = Number
    Period = Period
    Return = Return
    Simulation = Simulation
    String = String
    # Structure = Structure
    tax_benefit_system = None
    # TaxScalesTree = TaxScalesTree
    Tuple = Tuple
    Type = Type
    # UniformDictionary = UniformDictionary
    # UniformIterator = UniformIterator
    # UniformList = UniformList
    Variable = Variable

    def __init__(self, driver = None, tax_benefit_system = None):
        self.driver = driver
        self.tax_benefit_system = tax_benefit_system

    def parse_power(self, node, container = None):
        assert isinstance(node, lib2to3.pytree.Base), "Invalid node:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        assert isinstance(container, AbstractWrapper), "Invalid container {} for node:\n{}\n\n{}".format(container,
            repr(node), unicode(node).encode('utf-8'))

        assert node.type == symbols.power, "Unexpected power type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) >= 2, "Unexpected length {} of children in power:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        header = children[0]
        assert header.type == tokens.NAME, "Unexpected header type:\n{}\n\n{}".format(repr(header),
            unicode(header).encode('utf-8'))
        subject = container.get_variable(header.value, default = None, parser = self)
        assert subject is not None, "Undefined variable: {}".format(header.value)
        for trailer in itertools.islice(children, 1, None):
            assert trailer.type == symbols.trailer, "Unexpected trailer type:\n{}\n\n{}".format(repr(trailer),
                unicode(trailer).encode('utf-8'))
            trailer_children = trailer.children
            trailer_first_child = trailer_children[0]
            if trailer_first_child.type == tokens.DOT:
                subject = self.Attribute.parse(subject, trailer, container = container, parser = self)
            elif trailer_first_child.type == tokens.LPAR:
                if len(trailer_children) == 2:
                    left_parenthesis, right_parenthesis = trailer_children
                    arguments = None
                else:
                    assert len(trailer_children) == 3, \
                        "Unexpected length {} of children in power call:\n{}\n\n{}".format(len(trailer_children),
                        repr(trailer), unicode(trailer).encode('utf-8'))
                    left_parenthesis, arguments, right_parenthesis = trailer_children
                assert left_parenthesis.type == tokens.LPAR, "Unexpected left parenthesis type:\n{}\n\n{}".format(
                    repr(left_parenthesis), unicode(left_parenthesis).encode('utf-8'))
                assert right_parenthesis.type == tokens.RPAR, "Unexpected right parenthesis type:\n{}\n\n{}".format(
                    repr(right_parenthesis), unicode(right_parenthesis).encode('utf-8'))
                subject = self.Call.parse(subject, arguments, container = container, parser = self)
            else:
                subject = self.Key.parse(subject, trailer, container = container, parser = self)
        return subject

    def parse_value(self, node, container = None):
        assert isinstance(node, lib2to3.pytree.Base), "Invalid node:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        assert isinstance(container, AbstractWrapper), "Invalid container {} for node:\n{}\n\n{}".format(container,
            repr(node), unicode(node).encode('utf-8'))

        children = node.children
        if node.type == symbols.and_expr:
            assert len(children) >= 3 and (len(children) & 1), \
                "Unexpected length {} of children in and_expr:\n{}\n\n{}".format(len(children), repr(node),
                unicode(node).encode('utf-8'))
            return None  # TODO
        if node.type == symbols.arith_expr:
            assert len(children) >= 3 and (len(children) & 1), \
                "Unexpected length {} of children in arith_expr:\n{}\n\n{}".format(len(children), repr(node),
                unicode(node).encode('utf-8'))
            return None  # TODO
        if node.type == symbols.atom:
            assert len(children) == 3, "Unexpected length {} of children in atom:\n{}\n\n{}".format(
                len(children), repr(node), unicode(node).encode('utf-8'))
            return None  # TODO
        if node.type == symbols.comparison:
            assert len(children) == 3, "Unexpected length {} of children in comparison:\n{}\n\n{}".format(
                len(children), repr(node), unicode(node).encode('utf-8'))
            return None  # TODO
        if node.type == symbols.expr:
            assert len(children) >= 3 and (len(children) & 1), \
                "Unexpected length {} of children in expr:\n{}\n\n{}".format(len(children), repr(node),
                unicode(node).encode('utf-8'))
            return None  # TODO
        if node.type == symbols.factor:
            assert len(children) == 2, "Unexpected length {} of children in factor:\n{}\n\n{}".format(len(children),
                repr(node), unicode(node).encode('utf-8'))
            return None  # TODO
        if node.type == symbols.power:
            return self.parse_power(node, container = container)
        if node.type == symbols.term:
            assert len(children) >= 3 and (len(children) & 1), \
                "Unexpected length {} of children in term:\n{}\n\n{}".format(len(children), repr(node),
                unicode(node).encode('utf-8'))
            return None  # TODO
        if node.type == symbols.test:
            assert len(children) == 5, "Unexpected length {} of children in test:\n{}\n\n{}".format(
                len(children), repr(node), unicode(node).encode('utf-8'))
            assert children[1].type == tokens.NAME and children[1].value == 'if', \
                "Unexpected non-if token in test:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            assert children[3].type == tokens.NAME and children[3].value == 'else', \
                "Unexpected non-else token in test:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            return None  # TODO
        if node.type == symbols.testlist:
            return self.Tuple.parse(node, container = container, parser = self)
        if node.type == tokens.NAME:
            variable = container.get_variable(node.value, default = None, parser = self)
            assert variable is not None, "Undefined variable: {}".format(node.value)
            return variable
        if node.type == tokens.NUMBER:
            return self.Number.parse(node, container = container, parser = self)
        if node.type == tokens.STRING:
            return self.String.parse(node, container = container, parser = self)
        assert False, "Unexpected value:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))

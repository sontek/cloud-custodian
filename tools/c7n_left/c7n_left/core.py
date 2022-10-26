# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
#
import fnmatch
import logging
import sys

from c7n.actions import ActionRegistry
from c7n.cache import NullCache
from c7n.filters import FilterRegistry
from c7n.manager import ResourceManager

from c7n.provider import Provider, clouds
from c7n.policy import PolicyExecutionMode
from .utils import load_policies
from collections import defaultdict


log = logging.getLogger("c7n.iac")


class IACSourceProvider(Provider):

    display_name = "IAC"

    def get_session_factory(self, options):
        return lambda *args, **kw: None

    def initialize(self, options):
        pass

    def initialize_policies(self, policies, options):
        return policies


class CollectionRunner:
    def __init__(self, policy_dir, options, reporter):
        self.policy_dir = policy_dir
        self.options = options
        self.reporter = reporter

    def run(self):
        event = self.get_event()
        provider = self.get_provider()

        if not provider.match_dir(self.options.source_dir):
            raise NotImplementedError(
                "no %s source files found" % provider.provider_name
            )

        graph = provider.parse(self.options.source_dir)
        policies = load_policies(self.policy_dir, self.options)
        if not policies:
            log.warning("no policies found")
            sys.exit(1)

        for p in policies:
            p.expand_variables(p.get_variables())
            p.validate()

        self.reporter.on_execution_started(policies)
        # consider inverting this order to allow for results grouped by policy
        # at the moment, we're doing results grouped by resource.
        found = False
        for rtype, resources in graph.get_resources_by_type():
            for p in policies:
                if not self.match_type(rtype, p):
                    continue
                result_set = self.run_policy(p, graph, resources, event)
                if result_set:
                    self.reporter.on_results(result_set)
                    found = True
        self.reporter.on_execution_ended()
        return found

    def run_policy(self, policy, graph, resources, event):
        event = dict(event)
        event.update({"graph": graph, "resources": resources})
        return policy.push(event)

    def get_provider(self):
        provider_name = self.options.provider
        provider = clouds[provider_name]()
        return provider

    def get_event(self):
        return {"config": self.options}

    @staticmethod
    def match_type(rtype, p):
        if isinstance(p.resource_type, str):
            return fnmatch.fnmatch(rtype, p.resource_type.split(".", 1)[-1])
        if isinstance(p.resource_type, list):
            for pr in p.resource_type:
                return fnmatch.fnmatch(rtype, pr.split(".", 1)[-1])


class IACSourceMode(PolicyExecutionMode):
    @property
    def manager(self):
        return self.policy.resource_manager

    def run(self, event, ctx):
        if not self.policy.is_runnable(event):
            return []

        resources = event["resources"]
        resources = self.manager.filter_resources(resources, event)
        return self.as_results(resources)

    def as_results(self, resources):
        return ResultSet([PolicyResourceResult(r, self.policy) for r in resources])


class ResultSet(list):
    pass


class PolicyResourceResult:
    def __init__(self, resource, policy):
        self.resource = resource
        self.policy = policy


class IACResourceManager(ResourceManager):

    filter_registry = FilterRegistry("iac.filters")
    action_registry = ActionRegistry("iac.actions")
    log = log

    def __init__(self, ctx, data):
        self.ctx = ctx
        self.data = data
        self._cache = NullCache(None)
        self.session_factory = lambda: None
        self.filters = self.filter_registry.parse(self.data.get("filters", []), self)
        self.actions = self.action_registry.parse(self.data.get("actions", []), self)

    def get_resource_manager(self, resource_type, data=None):
        return self.__class__(self.ctx, data or {})


class IACResourceMap(object):

    resource_class = None

    def __init__(self, prefix):
        self.prefix = prefix

    def __contains__(self, k):
        if k.startswith(self.prefix):
            return True
        return False

    def __getitem__(self, k):
        if k.startswith(self.prefix):
            return self.resource_class
        raise KeyError(k)

    def __iter__(self):
        return iter(())

    def notify(self, *args):
        pass

    def keys(self):
        return ()

    def items(self):
        return ()

    def get(self, k, default=None):
        # that the resource is in the map has alerady been verified
        # we get the unprefixed resource on get
        return self.resource_class


class ResourceGraphReferenceIndex:
    """
    This is a generic indexing class that allows us to store
    references between resources in a ResourceGraph while providing
    a quick lookup point to build out filters for c7n core.
    """
    def __init__(self):
        # The resources index is a place to store all references
        # to other resources in a fast lookup table.
        # {<resource_id>: {<resource_type>: [<resource_id>] } }
        # For example...
        #    "<s3_bucket_id>":
        #        "aws_s3_bucket_server_side_encryption_configuration": [<sse_id>]
        #
        #    "<sse_id>:
        #       "aws_s3_bucket": [s3_bucket_id]
        self.resource_index = defaultdict(dict)

        # {<resource_type>: <related_resource_type>: <lookup_key>}
        # For example:
        #   "<aws_s3_bucket_sse>:
        #       "<aws_s3_bucket>": "bucket"
        self.registry = defaultdict(dict)

    def add_reference(
        self,
        base_resource_type,
        base_resource_id,
        related_resource_type,
        related_resource_id,
        related_id_expression,
    ):
        # We store the inverse of the reference so we can get it from either side.
        if related_resource_type not in self.resource_index[base_resource_id]:
            self.resource_index[base_resource_id][related_resource_type] = []
        self.resource_index[base_resource_id][related_resource_type].append(related_resource_id)

        if base_resource_type not in self.resource_index[related_resource_id]:
            self.resource_index[related_resource_id][base_resource_type] = []
        self.resource_index[related_resource_id][base_resource_type].append(base_resource_id)

        # We cannot store the inverse for the property registry because that information
        # actually isn't represented in the dataset from `tfparse`
        self.registry[base_resource_type][related_resource_type] = related_id_expression


class ResourceGraph:
    def __init__(self, resource_data, src_dir):
        self.resource_data = resource_data
        self.src_dir = src_dir

    def get_resources_by_type(self, types=(), references_index=None):
        raise NotImplementedError()

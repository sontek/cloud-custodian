# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
#

from tfparse import load_from_path

from c7n.provider import clouds
from c7n.policy import execution
from c7n.utils import type_schema

from ...core import (
    IACResourceManager,
    IACResourceMap,
    IACSourceProvider,
    IACSourceMode,
    ResourceGraphReferenceIndex,
    log,
)
from ...related import RelatedResourceFilter
from .graph import TerraformGraph


class TerraformResourceManager(IACResourceManager):
    pass


class TerraformResourceMap(IACResourceMap):
    resource_class = TerraformResourceManager


@clouds.register("terraform")
class TerraformProvider(IACSourceProvider):

    display_name = "Terraform"
    resource_prefix = "terraform"
    resource_map = TerraformResourceMap(resource_prefix)
    resources = resource_map

    def initialize_policies(self, policies, options):
        for p in policies:
            p.data["mode"] = {"type": "terraform-source"}
        return policies

    def parse(self, source_dir):
        resource_data = load_from_path(source_dir)
        graph = TerraformGraph(resource_data, source_dir)
        references = ResourceGraphReferenceIndex()
        # We need to traverse the graph one time to get all the references
        # so we can generate the filter registry.
        [_ for _ in graph.get_resources_by_type(references_index=references)]
        log.debug("Loaded %d resources", len(graph))
        related_filter = RelatedResourceFilter(references)
        TerraformResourceManager.filter_registry.register(
            "related_resource",
            related_filter,
        )

        return graph

    def match_dir(self, source_dir):
        files = list(source_dir.glob("*.tf"))
        files += list(source_dir.glob("*.tf.json"))
        return files


@execution.register("terraform-source")
class TerraformSource(IACSourceMode):

    schema = type_schema("terraform-source")

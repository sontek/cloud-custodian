# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
#

from ...core import ResourceGraph
from .resource import TerraformResource


class TerraformGraph(ResourceGraph):
    def __len__(self):
        return sum(map(len, self.resource_data.values()))

    def get_resources_by_type(self, types=(), references_index=None):
        if isinstance(types, str):
            types = (types,)
        for type_name, type_items in self.resource_data.items():
            if types and type_name not in types:
                continue
            if type_name == "data":
                for data_type, data_items in type_items.items():
                    resources = []
                    for name, data in data_items.items():
                        resources.append(self.as_resource(name, data, references_index))
                    yield "%s.%s" % (type_name, data_type), resources
            elif type_name == "moved":
                yield type_name, self.as_resource(type_name, data, references_index)
            elif type_name == "locals":
                yield type_name, self.as_resource(type_name, data, references_index)
            elif type_name == "terraform":
                yield type_name, self.as_resource(type_name, data, references_index)
            else:
                resources = []
                for data in type_items:
                    name = data["__tfmeta"]["path"]
                    resources.append(self.as_resource(name, data, references_index))
                yield type_name, resources

    def as_resource(self, name, data, references_index):
        if isinstance(data["__tfmeta"], list):
            for m in data["__tfmeta"]:
                m["src_dir"] = self.src_dir
        else:
            data["__tfmeta"]["src_dir"] = self.src_dir

        # TODO: Since `get_resources_by_type` is a generator we need to evaluate the
        # entire graph to build up the index.  Which means we currently can't store
        # these references on the graph.   It probably makes sense to change this? Although
        # it could be expensive to store all resources in-memory as well.
        if references_index:
            # TODO: This is not ideal but `tfparse` stores the `__ref__` as a value
            # on the attribute, so we need to look at all properties to see if it is
            # an object with `__ref__` in it.
            for key, value in data.items():
                if isinstance(value, dict) and '__ref__' in value:
                    # __ref__ will come from `tfparse` looking like this:
                    # {'__name__': 'cool-dynamo-table',
                    #      '__ref__': 'b3ca17a0-d467-4c08-8fb0-bb2738f4e149',
                    #      '__type__': 'aws_dynamodb_table'},
                    references_index.add_reference(
                        data["__tfmeta"]["label"],
                        data["id"],
                        value["__type__"],
                        value["__ref__"],
                        key,
                    )
        return TerraformResource(name, data)

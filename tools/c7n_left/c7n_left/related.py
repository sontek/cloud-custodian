from c7n.filters import ValueFilter
from collections import defaultdict
import jmespath


def RelatedResourceFilter(reference_index):
    class _RelatedResourceFilter(ValueFilter):
        references = reference_index

        def get_related(self, resources, event):
            # Resources is the base resource.  So for example if you are on
            # an s3 bucket and trying to identify that there is a related
            # server_side_encryption_configuration, `resources` is the list
            # of s3 buckets.
            target_resources = None

            for rtype, potential_targets in event['graph'].get_resources_by_type():
                # We have some resources on our graph that are of the target type.
                # Exit early because these are the only resources we need to look at.
                if rtype == self.data['type']:
                    target_resources = potential_targets
                    break

            if not target_resources:
                return {}

            target_resources_by_id = {
                r['id']: r for r in target_resources
            }

            related_resources = defaultdict(list)
            # Now we need to find any of the target resource that have a link
            # back to our base resource.   This will be a list of base resource IDs
            # that were found in our target.
            for base_resource in resources:
                # This resource has no references.  Early exit.
                base_id = base_resource['id']
                if base_id not in self.references.resource_index:
                    continue

                target_ids = self.references.resource_index[base_id][self.data['type']]
                for target_id in target_ids:
                    target = target_resources_by_id[target_id]
                    related_resources[base_id].append(target)

            return related_resources

        def process_resource(self, resource, related):
            # This function is now used to filter down the related resources
            # based on the filter epxressions passed. Return `True` if it matches
            # otherwise return `False`
            for r in related:
                # TODO.. This needs to do all the proper matching with
                # op, value_type, etc.
                value = jmespath.search(
                    "%s" % self.data["key"],
                    r
                )
                # We didn't match the key they were looking for and
                # theya re using the special "absent" value.
                if value is None and self.data["value"] == "absent":
                    return True

                if value == self.data["value"]:
                    return True
            return False

        def process(self, resources, event):
            related = self.get_related(resources, event)
            found = []
            for r in resources:
                # Pass a list of `None` in here so there is still an
                # object to match on.  So in the case where they say
                # "key is absent" we can check if that is true.
                result = related.get(r['id']) or [None]
                if self.process_resource(r, result):
                    found.append(r)
            return found

    return _RelatedResourceFilter

from c7n.filters import ValueFilter
from collections import defaultdict
import jmespath


def RelatedResourceFilter(related_resource, related_ids_expression):
    class _RelatedResourceFilter(ValueFilter):
        RelatedResource = related_resource
        RelatedIdsExpression = related_ids_expression

        def get_related(self, resources, event):
            # Resources is the base resource.  So for example if you are on
            # an s3 bucket and trying to identify that there is a related
            # server_side_encryption_configuration, `resources` is the list
            # of s3 buckets.
            target_resources = None
            for rtype, potential_targets in event['graph'].get_resources_by_type():
                # We have some resources on our graph that are of the target type.
                # Exit early because these are the only resources we need to look at.
                if rtype == self.RelatedResource:
                    target_resources = potential_targets
                    break

            if not target_resources:
                return []

            # Now we need to find any of the target resource that have a link
            # back to our base resource.   This will be a list of base resource IDs
            # that were found in our target.
            related_resources = defaultdict(list)
            base_resource_ids = set([r['id'] for r in resources])

            for target in target_resources:
                base_id = jmespath.search(
                    "%s" % self.RelatedIdsExpression,
                    target
                )
                if base_id in base_resource_ids:
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
                if value == self.data["value"]:
                    return True
            return False

        def process(self, resources, event):
            related = self.get_related(resources, event)
            return [r for r in resources if self.process_resource(r, related[r['id']])]

    return _RelatedResourceFilter

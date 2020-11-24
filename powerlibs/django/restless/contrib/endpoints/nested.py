from cached_property import cached_property
from powerlibs.django.restless.models import serialize_model
from powerlibs.django.restless.http import Http400, HttpError
from django.core.exceptions import FieldError
from django.db.models import F


class NestedEntitiesMixin:
    @cached_property
    def foreign_keys(self):
        fields = []
        for field in self.model._meta.fields:
            class_name = field.__class__.__name__
            if class_name == 'ForeignKey':
                fields.append(field.name)

        return fields

    @staticmethod
    def get_hidden_fields(model):
        fields = []
        for field in model._meta.fields:
            class_name = field.__class__.__name__
            if class_name == 'PasswordField' or field.name == 'password':
                fields.append(field.name)

        return fields


class NestedEntitiesDetailEndpointMixin(NestedEntitiesMixin):
    def get(self, request, *args, **kwargs):
        serialized_data = super().get(request, *args, **kwargs)

        nesting_request = request.GET.get('_nested', None)
        if nesting_request:
            serialized_data['_related'] = related_entities = {}
            instance = self.get_instance(request, *args, **kwargs)

            for entity_name in nesting_request.split(','):
                if entity_name in self.foreign_keys:
                    entity = getattr(instance, entity_name)

                    if entity:
                        serialized_entity = serialize_model(
                            entity, exclude=self.get_hidden_fields(entity._meta.model))
                    else:
                        serialized_entity = None

                    related_entities[entity_name] = serialized_entity
                    continue

                field = getattr(instance, entity_name, None)

                if field and field.__class__.__name__ == 'ManyRelatedManager':
                    the_list = related_entities[entity_name] = []

                    for entity in field.all():
                        the_list.append(serialize_model(
                            entity, exclude=self.get_hidden_fields(entity._meta.model)))

        return serialized_data


class NestedEntitiesListEndpointMixin(NestedEntitiesMixin):
    def get_query_set(self, request, *args, **kwargs):
        queryset = super().get_query_set(request, *args, **kwargs)

        nesting_request = request.GET.get('_nested', None)
        if nesting_request:
            for entity in nesting_request.split(','):
                split = entity.split('@')
                entity_name = split[0]
                entity_fields = []

                try:
                    entity_fields = split[1].split('|')
                except IndexError:
                    raise HttpError(
                        400, "User '@' to specify {} fields, split multiple fields using '|'".format(entity_name))

                try:
                    queryset = queryset.select_related(entity_name)
                except FieldError as ex:
                    raise HttpError(400, "FieldError: {}".format(ex))

                annotated_queryset = queryset
                for field in entity_fields:
                    fullField = f"{entity_name}__{field}"
                    annotated_queryset = annotated_queryset.annotate(
                        **{fullField: F(fullField)})

                return annotated_queryset

        return queryset.values()

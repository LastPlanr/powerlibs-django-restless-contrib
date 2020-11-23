import ast
from django.core.exceptions import FieldError
from django.core.validators import ValidationError
from django.db.models import Q

from powerlibs.django.restless.http import Http400, HttpError


class PaginatedEndpointMixin:
    def get(self, request, *args, **kwargs):
        limit = request.GET.get('_limit', None)
        offset = int(request.GET.get('_offset', 0))

        qs = self.get_query_set(request, *args, **kwargs)
        total = qs.count()

        begin = offset
        if limit is None:
            end = None
        else:
            end = begin + int(limit)
        paginated_qs = qs[begin:end]

        count = paginated_qs.count()
        serialized_results = self.serialize(paginated_qs)

        return {
            'total': total,
            'count': count,
            'results': serialized_results,
        }


class OrderedEndpointMixin:
    def get_query_set(self, request, *args, **kwargs):
        queryset = super().get_query_set(request, *args, **kwargs)

        orderby_field = request.GET.get('_orderby', None)
        if orderby_field:
            try:
                queryset = queryset.order_by(orderby_field)
            except FieldError as ex:
                return Http400("FieldError: {}".format(ex))

        return queryset


class FilteredEndpointMixin:
    def get_query_set(self, request, *args, **kwargs):
        queryset = super().get_query_set(request, *args, **kwargs)

        filter_args = {}
        exclude_filter_args = {}
        filter_clauses = []
        exclude_clauses = []

        for key, value in request.GET.items():
            if key.startswith('_'):
                continue

            if key == 'OP' or key.startswith('OP_'):
                if filter_args:
                    filter_clauses.append(filter_args)
                    filter_clauses.append(value)
                    filter_args = {}

                if exclude_filter_args:
                    exclude_clauses.append(exclude_filter_args)
                    exclude_clauses.append(value)
                    exclude_filter_args = {}

                continue

            args_list = filter_args

            try:
                splitRes = key.split('__')
                potential_operator = splitRes[-1]
            except IndexError:
                pass
            else:
                if potential_operator == 'in':
                    value = value.split(',')
                elif potential_operator == 'not_in':
                    value = value.split(',')
                    key = key.replace('not_in', 'in')
                    args_list = exclude_filter_args
                elif potential_operator == 'ne':
                    key = key.replace('__ne', '')
                    args_list = exclude_filter_args

            if value == 'True':
                value = True
            elif value == 'False':
                value = False
            elif isinstance(value, str) and value.strip().startswith('['):
                value = ast.literal_eval(value.strip())

            args_list[key] = value

        if filter_args:
            filter_clauses.append(filter_args)

        if exclude_filter_args:
            exclude_clauses.append(exclude_filter_args)

        filter_Qs = None
        exclude_filter_Qs = None

        if filter_clauses:
            for clause in filter_clauses:
                if clause == 'OR':
                    continue

                if clause == 'AND':
                    if filter_Qs:
                        queryset = queryset.filter(filter_Qs)
                        filter_Qs = None
                    continue

                if filter_Qs is None:
                    filter_Qs = Q(**clause)
                else:
                    filter_Qs |= Q(**clause)

            if filter_Qs:
                queryset = queryset.filter(filter_Qs)

        if exclude_clauses:
            for clause in exclude_clauses:
                if clause == 'OR':
                    continue

                if clause == 'AND':
                    if exclude_filter_Qs:
                        queryset = queryset.exclude(exclude_filter_Qs)
                        exclude_filter_Qs = None
                    continue

                if exclude_filter_Qs is None:
                    exclude_filter_Qs = Q(**clause)
                else:
                    exclude_filter_Qs |= Q(**clause)

            if exclude_filter_Qs:
                queryset = queryset.exclude(exclude_filter_Qs)

        return queryset


class SoftDeletableDetailEndpointMixin:
    def delete(self, request, *args, **kwargs):
        instance = self.get_instance(request, *args, **kwargs)

        old_deleted_status = instance.deleted
        if not old_deleted_status:
            instance.deleted = True
            instance.save()

        return {}


class SoftDeletableListEndpointMixin:
    def get_query_set(self, request, *args, **kwargs):
        queryset = super().get_query_set(request, *args, **kwargs)
        return queryset.filter(deleted=False)


class BaseEndpointMixin:
    def get_query_set(self, request, *args, **kwargs):
        try:
            queryset = super().get_query_set(request, *args, **kwargs)
        except ValidationError as ex:
            raise HttpError(400, f"ValidationError: {ex}")

        return queryset

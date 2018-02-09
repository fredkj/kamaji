# -*- coding: utf-8 -*-

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from rest_framework import serializers
from rest_framework.relations import HyperlinkedRelatedField

from shared.fields import URITemplateRelatedField
from shared.rest_validators import IsSSHKey, MUST_BE_UNIQUE_MESSAGE
from user_management.models import (
    ProjectGroup, GlobalGroup, Project, Role
)


def validate_role(value):
    if not Role.objects.filter(name=value).exists():
        raise serializers.ValidationError(
            "Role {0} doesn't exist.".format(value))
    return value


class ProjectGroupSerializer(serializers.ModelSerializer):
    class NestedProjectSerializer(serializers.RelatedField):
        def to_representation(self, instance):
            return instance.name

        def to_internal_value(self, data):
            return Project.objects.get(name=data)

    class Meta:
        model = ProjectGroup
        fields = ('id', 'name', 'project', 'role', 'users')
        read_only_fields = ('name', )

    role = serializers.SlugRelatedField(
        slug_field='name',
        queryset=Role.objects.all(),
        help_text='Role to be coupled with the group'
    )
    project = NestedProjectSerializer(
        queryset=Project.objects.all(),
        help_text='Project to couple with the group'
    )


class GlobalGroupSerializer(serializers.ModelSerializer):
    role = serializers.SlugRelatedField(
        slug_field='name',
        queryset=Role.objects.all(),
        help_text='Role to couple with group'
    )

    class Meta:
        model = GlobalGroup
        fields = ('id', 'name', 'role', 'users')


class ProjectSerializer(serializers.ModelSerializer):
    name = serializers.CharField(help_text='Name of the project')

    description = serializers.CharField(
        help_text='Brief description of the project'
    )

    enabled = serializers.BooleanField(
        help_text='Enable or disable project',
        default=True,
        initial=True
    )

    groups_link = HyperlinkedRelatedField(
        read_only=True,
        view_name='projectgroup_per_project',
        lookup_url_kwarg='project',
        source='*'
    )

    instances_link = HyperlinkedRelatedField(
        read_only=True,
        view_name='instancesbyprojects',
        lookup_url_kwarg='project_id',
        source='*'
    )

    volumes_link = HyperlinkedRelatedField(
        read_only=True,
        view_name='volumes',
        lookup_url_kwarg='project_id',
        source='*'
    )

    users_link = HyperlinkedRelatedField(
        read_only=True,
        view_name='users_per_project',
        lookup_url_kwarg='project',
        source='*'
    )

    membership_link_template = URITemplateRelatedField(
        view_name='project_memberships',
        assigned_parameters={
            'project_id': 'id'
        },
        templated_parameters=('username', )
    )

    def create(self, validated_data):
        return Project.objects.create(**validated_data)

    def validate_name(self, name):
        if Project.objects.filter(name=name).exists():
            raise serializers.ValidationError(
                'There is already a project with name {0}'.format(name)
            )
        return name

    class Meta:
        model = Project
        fields = (
            'id',
            'name',
            'description',
            'enabled',
            'groups_link',
            'instances_link',
            'volumes_link',
            'users_link',
            'membership_link_template'
        )


class UserSerializer(serializers.Serializer):
    """
    User serializer that should only be used for users with a kamajiuser
    assigned to them.
    project_roles are readonly.
    """
    id = serializers.IntegerField(required=False, read_only=True)
    username = serializers.CharField(max_length=100)
    first_name = serializers.CharField(max_length=250)
    last_name = serializers.CharField(max_length=250)
    email = serializers.EmailField(max_length=250)
    password = serializers.CharField(
        max_length=250,
        required=False,
        write_only=True
    )
    last_login = serializers.DateTimeField(read_only=True)

    project_roles = serializers.DictField(
        required=False,
        read_only=True
    )

    global_role = serializers.ChoiceField(
        choices={Role.GLOBAL_ADMINISTRATOR, Role.GLOBAL_SPECTATOR},
        required=False,
        allow_null=True
    )

    ssh_key = serializers.CharField(
        max_length=2000,
        required=False,
        validators=[IsSSHKey(allow_blank=True)],
        allow_null=True
    )

    def create(self, validated_data):
        ssh_key = validated_data.pop('ssh_key', None)
        global_role = validated_data.pop('global_role', None)

        try:
            user = User.objects.create_user(**validated_data)
        except IntegrityError:
            # We don't subclass the user model so we need to handle
            # creation errors here.
            raise serializers.ValidationError({
                'username': MUST_BE_UNIQUE_MESSAGE
            })

        user.kamajiuser.ssh_key = ssh_key
        user.kamajiuser.set_global_role(global_role)
        user.kamajiuser.save()

        return user

    def update(self, instance, validated_data):
        if 'password' in validated_data:
            instance.set_password(validated_data.pop('password'))

        if 'ssh_key' in validated_data:
            instance.kamajiuser.ssh_key = validated_data.pop('ssh_key')
            instance.kamajiuser.save(update_fields=['ssh_key'])

        if 'global_role' in validated_data:
            # We should only be passing in valid roles here, so don't
            # catch anything
            instance.kamajiuser.set_global_role(
                validated_data.pop('global_role')
            )

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        return instance

    def to_representation(self, instance):
        rep = super(UserSerializer, self).to_representation(instance)
        kamaji_user = instance.kamajiuser

        if kamaji_user.global_role is not None:
            rep['global_role'] = kamaji_user.global_role.name
        else:
            rep['global_role'] = None

        rep['ssh_key'] = kamaji_user.ssh_key
        rep['project_roles'] = {project.name: role.name for project, role in
                                kamaji_user.project_roles.items()}

        return rep


class ProjectMembershipSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.PROJECT_ROLES)


class PasswordChangeTokenSerializer(serializers.Serializer):
    token = serializers.CharField()

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(PasswordChangeTokenSerializer, self).__init__(*args, **kwargs)

    def validate_token(self, token):
        token_generator = PasswordResetTokenGenerator()

        if (self.user is None
                or not token_generator.check_token(self.user, token)):
            raise serializers.ValidationError('Invalid token')

        return token


class PasswordChangeSerializer(PasswordChangeTokenSerializer):
    new_password = serializers.CharField()


class ActionSerializer(serializers.Serializer):
    action = serializers.CharField()

    def __init__(self, **kwargs):
        self.actions = kwargs.pop('actions', None)
        super(ActionSerializer, self).__init__(**kwargs)

    def validate_action(self, value):
        if value not in self.actions:
            raise serializers.ValidationError(
                '{0} is not a defined action. Valid actions: {1}.'.format(
                    value,
                    ', '.join(self.actions)
                )
            )

        return value

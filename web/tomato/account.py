# -*- coding: utf-8 -*-

# ToMaTo (Topology management software) 
# Copyright (C) 2012 Integrated Communication Systems Lab, University of Kaiserslautern
#
# This file is part of the ToMaTo project
#
# ToMaTo is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import random, string, json

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django import forms
from admin_common import organization_name_list
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from django.utils.html import conditional_escape

from lib import wrap_rpc, getapi, AuthError, serverInfo

from admin_common import BootstrapForm, ConfirmForm, RemoveConfirmForm, FixedList, FixedText, Buttons, append_empty_choice
from tomato.crispy_forms.layout import Layout
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _



CategoryTranslationDict = {
		   'manager_user_global':'Global User Management',
		   'manager_user_orga':'Organization-Internal User Management',
		   'manager_host_global':'Global Host Management',
		   'manager_host_orga':'Organization-Internal Host Management',
		   'user':'User',
		   'error_management':"Error Management",
		   'other':'Other'
		}

category_order = [
		'manager_user_global',
		'manager_user_orga',
		'manager_host_global',
		'manager_host_orga',
		'error_management',
		'user'
	]

def render_account_flag_fixedlist(api, value, flags=None, flag_categories=None):
	FlagTranslationDict = flags or api.account_flags()
	categories = flag_categories or api.account_flag_categories()
	
	catlist = category_order
	for cat in categories.keys():
		if not cat in catlist:
			catlist.append(cat)
	
	output = []
	isFirst = True
	
	for cat in catlist:
		if cat in categories: #categories come from the backend, cat from the frontend. ignore categories which are not used by the backend.
			foundOne = False
			for v in categories[cat]:
				if v in value:
					if not foundOne:
						if not isFirst:
							output.append('</ul>')
						else:
							isFirst = False
						output.append('<ul>')
						output.append('<b>' + CategoryTranslationDict.get(cat,cat) + '</b>')
						foundOne = True
					output.append('<li style="margin-left:20px;">' + FlagTranslationDict.get(v,v) + '</li>')
		
	return output
			
			
			
class AccountFlagFixedList(FixedList):
	api = None
	def render(self, name, value, attrs=None):
		output = render_account_flag_fixedlist(self.api, value)
		return forms.MultipleHiddenInput.render(self, name, value) + mark_safe(u'\n'.join(output))
	
	def __init__(self, api, *args, **kwargs):
		super(AccountFlagFixedList, self).__init__(*args, **kwargs)
		self.api = api
		

class AccountFlagCheckboxList(forms.widgets.CheckboxSelectMultiple):
	inline_class=""
	api = None
	def render(self, name, value, attrs=None):
		if value is None: value = []
		has_id = attrs and 'id' in attrs
		final_attrs = self.build_attrs(attrs, name=name)
		str_values = set([force_unicode(v) for v in value])
	
		FlagTranslationDict = self.api.account_flags()
		categories = self.api.account_flag_categories()
		catlist = category_order
		
		output = []
		isFirst = True
		for cat in categories.keys():
			if not cat in catlist:
				catlist.append(cat)
		
		for cat in catlist:
			if cat in categories: #categories come from the backend, cat from the frontend. ignore categories which are not used by the backend.
				foundOne = False
				for v in categories[cat]:
					if not foundOne:
						if not isFirst:
							output.append('<br />')
						else:
							isFirst = False
						output.append('<b>' + CategoryTranslationDict.get(cat,cat) + '</b>')
						foundOne = True
						
					if has_id:
						final_attrs = dict(final_attrs, id='%s_%s' % (attrs['id'], self.choices.index((v,FlagTranslationDict.get(v,v)))))
						label_for = u' for="%s"' % final_attrs['id']
					else:
						label_for = ''
						
					cb = forms.widgets.CheckboxInput(final_attrs, check_test=lambda value: value in str_values)
					option_value = force_unicode(v)
					rendered_cb = cb.render(name, option_value)
					option_label = conditional_escape(force_unicode(FlagTranslationDict.get(v,v)))
					output.append(u'<label style="font-weight:normal;" class="checkbox%s">' % (self.inline_class))
					output.append(rendered_cb.replace("form-control", "") + option_label)
					output.append('</label>')
		output.append('</ul>')
		return mark_safe(u'\n'.join(output))
	
	def __init__(self, api, *args, **kwargs):
		super(AccountFlagCheckboxList, self).__init__(*args, **kwargs)
		self.api = api
		self.choices = api.account_flags().items()
	
class AccountForm(BootstrapForm):
	name = forms.CharField(label=_("Account name"), max_length=50)
	password = forms.CharField(label=_("Password"), widget=forms.PasswordInput, required=False)
	password2 = forms.CharField(label=_("Password (repeated)"), widget=forms.PasswordInput, required=False)
	organization = forms.CharField(max_length=50)
	origin = forms.CharField(label=_("Origin"), widget=forms.HiddenInput, required=False)
	realname = forms.CharField(label=_("Full name"))
	email = forms.EmailField()
	flags = forms.MultipleChoiceField(required=False)
	_reason = forms.CharField(widget = forms.Textarea, required=False, label=_("Reason for Registering"))
	send_mail = forms.BooleanField(label=_("Inform user"), required=False, initial=True)
	def __init__(self, api, *args, **kwargs):
		super(AccountForm, self).__init__(*args, **kwargs)
		self.fields["organization"].widget = forms.widgets.Select(choices=append_empty_choice(organization_name_list(api)))
		
	def clean_password(self):
		if self.data.get('password') != self.data.get('password2'):
			raise forms.ValidationError(_('Passwords are not the same'))
		return self.data.get('password')
	
	def clean(self, *args, **kwargs):
		self.clean_password()
		return forms.Form.clean(self, *args, **kwargs)

class AccountChangeForm(AccountForm):
	def __init__(self, api, data):
		AccountForm.__init__(self, api, data)
		flags = api.account_flags().items()
		self.fields["name"].widget = FixedText()
		del self.fields["origin"]
		del self.fields["_reason"]
		self.fields["flags"].choices = flags
		if api.user.isAdmin(data["organization"]):
			self.fields["flags"].widget = AccountFlagCheckboxList(api)
		else:
			self.fields["flags"].widget = AccountFlagFixedList(api)
			
		self.helper.form_action = reverse(edit, kwargs={'id':data['name']})
		self.helper.layout = Layout(
			'name',
			'password',
			'password2',
			'organization',
			'realname',
			'email',
			'flags',
			'send_mail',
			Buttons.cancel_save
		)
			

class AccountRegisterForm(AccountForm):
	aup = forms.BooleanField(label="", required=True)
	
	def __init__(self, api, data=None):
		AccountForm.__init__(self, api, data)
		self.fields["password"].required = True
		del self.fields["flags"]
		del self.fields["origin"]
		del self.fields["send_mail"]
		self.fields['aup'].label = _('I accept the') + '<a href="'+ serverInfo()['external_urls']['aup'] +'" target="_blank">' + _('acceptable use policy') + '</a>'
		self.helper.form_action = reverse(register)
		self.helper.layout = Layout(
			'name',
			'password',
			'password2',
			'organization',
			'realname',
			'email',
			'_reason',
			'aup',
			Buttons.cancel_save
		)

class AdminAccountRegisterForm(AccountForm):
	aup = forms.BooleanField(label="", required=True)
	
	def __init__(self, api, data=None):
		AccountForm.__init__(self, api, data)
		self.fields["password"].required = True
		del self.fields["flags"]
		del self.fields["origin"]
		del self.fields["aup"]
		del self.fields["password"]
		del self.fields["password2"]
		del self.fields["send_mail"]
		self.helper.form_action = reverse(register)
		self.helper.layout = Layout(
			'name',
			'organization',
			'realname',
			'email',
			Buttons.cancel_save
		)

@wrap_rpc
def list(api, request, with_flag=None, organization=True):
	if not api.user:
		raise AuthError()
	organization_description = None
	if organization is True:
		organization = api.user.organization
	if organization:
		organization_description = api.organization_info(organization)['description']
	accs = api.account_list(organization=organization)
	orgas = api.organization_list()
	flags = api.account_flags()
	flag_categories = api.account_flag_categories()
	if with_flag:
		acclist_new = []
		for acc in accs:
			if with_flag in acc['flags']:
				acclist_new.append(acc)
		accs = acclist_new
	for acc in accs:
		acc['flags_name'] = mark_safe(u'\n'.join(render_account_flag_fixedlist(api,acc['flags'],flags=flags, flag_categories=flag_categories)))
	return render(request, "account/list.html", {'accounts': accs, 'orgas': orgas, 'with_flag': with_flag, 'organization':organization, 'organization_description':organization_description})

@wrap_rpc
def info(api, request, id=None):
	if not api.user:
		raise AuthError()
	user = api.account_info(id) if id else api.user.data
	account_flags = api.account_flags()
	organization = api.organization_info(user["organization"])
	user["reason"] = user.get("_reason")
	flags = []
	for flag in user["flags"] or []:
		if flag in account_flags:
			flags.append(account_flags[flag])
		else:
			flags.append(flag+" (unknown flag)")
	flaglist = mark_safe(u'\n'.join(render_account_flag_fixedlist(api,user['flags'] or [])))
	return render(request, "account/info.html", {"account": user, "organization": organization, "flags": flags, 'flaglist': flaglist})                   

@wrap_rpc
def accept(api, request, id):
	if not api.user:
		raise AuthError()
	user = api.account_info(id)
	flags = user["flags"]
	for flag in ["new_account", "over_quota"]:
		if flag in flags:
			flags.remove(flag)
	api.account_modify(id, attrs={"flags": flags})
	api.account_mail(id, subject=_("Account activated"), message=_("Your account has been activated by an administrator. Now you are ready to start your first topology. Please see the tutorials to learn how to use ToMaTo."), from_support=True)
	return HttpResponseRedirect(reverse("tomato.account.info", kwargs={"id": id}))

@wrap_rpc
def edit(api, request, id):
	if not api.user:
		raise AuthError()
	user = api.account_info(id)
	if request.method=='POST':
		form = AccountChangeForm(api, request.REQUEST)
		if form.is_valid():
			data = form.cleaned_data
			if not api.user.isAdmin(data["organization"]):
				del data["flags"]
				del data["organization"]
			del data["name"]
			del data["password2"]
			if not data["password"]:
				del data["password"]
			send_mail = data.get("send_mail", False)
			if "send_mail" in data:
				del data["send_mail"]
			api.account_modify(id, attrs=data)
			if send_mail:
				api.account_mail(id, subject=_("Account modified"), message=_("Your account has been modified by an administrator. Please check your account details for the changes."), from_support=True)
			return HttpResponseRedirect(reverse("tomato.account.info", kwargs={"id": id}))
	else:
		data = user.copy()
		data["send_mail"] = user["id"] != api.user.id
		form = AccountChangeForm(api, data)
	return render(request, "form.html", {"account": user, "form": form, "heading":_("Edit Account ")+user["id"]})
	
@wrap_rpc
def register(api, request):
	if request.method=='POST':
		form = AdminAccountRegisterForm(api, request.REQUEST) if api.user else AccountRegisterForm(api, request.REQUEST)
		if form.is_valid():
			data = form.cleaned_data
			username = data["name"]
			organization=data["organization"]
			del data["name"]
			del data["organization"]
			if api.user:
				password = ''.join(random.choice(2 * string.ascii_lowercase + string.ascii_uppercase + 2 * string.digits) for x in range(12))
			else:
				password = data["password"]
				del data["password"]
				del data["password2"]
				del data["aup"]
			try:
				account = api.account_create(username, password=password, organization=organization, attrs=data)
				if api.user:
					api.account_mail(username, 
						subject=_("Account creation"), 
						message=_("A new ToMaTo account has been created for you by an administrator with the username\n\n\t%s\n\n and the password\n\n\t%s\n\nPlease login using that username and password and change it to something you can remember.") % (username, password),
						from_support=True)
				else:
					request.session["auth"] = "%s:%s" % (username, password)
					api = getapi(request)
					request.session["user"] = api.user  
				return HttpResponseRedirect(reverse("tomato.account.info", kwargs={"id": account["name"]}))
			except:
				import traceback
				print traceback.print_exc()
				form._errors["name"] = form.error_class([_("This name is already taken")])
	else:
		form = AdminAccountRegisterForm(api) if api.user else AccountRegisterForm(api) 
	return render(request, "form.html", {"form": form, "heading":_("Register New Account")})

@wrap_rpc
def reset_password(api, request, id):
	if request.method == 'POST':
		form = ConfirmForm(request.POST)
		if form.is_valid():
			passwd = ''.join(random.choice(2 * string.ascii_lowercase + string.ascii_uppercase + 2 * string.digits) for x in range(12))
			api.account_modify(id, {"password": passwd})
			api.account_mail(id, subject=_("Password reset"), message=_("Your password has been reset by an administrator to\n\n\t%s\n\nPlease login using that password and change it to something you can remember.") % passwd, from_support=True)
			return HttpResponseRedirect(reverse("tomato.account.info", kwargs={"id": id}))
	form = ConfirmForm.build(reverse("tomato.account.reset_password", kwargs={"id": id}))
	return render(request, "form.html", {"heading": _("Reset Password"), "message_before": _("Are you sure you want to reset the password of the account '")+id+"'?", 'form': form})	

@wrap_rpc
def remove(api, request, id=None):
	if request.method == 'POST':
		form = RemoveConfirmForm(request.POST)
		if form.is_valid():
			api.account_remove(id)
			return HttpResponseRedirect(reverse("account_list"))
	form = RemoveConfirmForm.build(reverse("tomato.account.remove", kwargs={"id": id}))
	return render(request, "form.html", {"heading": _("Remove Account"), "message_before": _("Are you sure you want to remove the account '")+id+"'?", 'form': form})

@wrap_rpc
def usage(api, request, id): #@ReservedAssignment
	if not api.user:
		raise AuthError()
	usage=api.account_usage(id)
	return render(request, "main/usage.html", {'usage': json.dumps(usage), 'name': _('Account') + '%s' % id})

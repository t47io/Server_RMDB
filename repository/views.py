from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.template import RequestContext#, Template
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
# from django.core.urlresolvers import reverse
from django.shortcuts import render_to_response, redirect
# from django import forms

from rdatkit.datahandlers import RDATFile, RDATSection, ISATABFile
from rdatkit.secondary_structure import SecondaryStructure

from rmdb.repository.models import *
from rmdb.repository.settings import *
from helpers import *
from helper_api import *
from helper_deposit import *
from helper_display import *
from helper_predict import *
from helper_register import *
from helper_stats import *

from itertools import chain
import time
# from sys import stderr


def index(request):
	news = NewsItem.objects.all().order_by('-date')[:10]
	entries = RMDBEntry.objects.all().order_by('-creation_date')[:10]
	for e in entries:
		e.constructs = ConstructSection.objects.filter(entry=e).values('name').distinct()
		e.cid = ConstructSection.objects.filter(entry=e).values( 'id' )[ 0 ][ 'id' ]

	(N_all, N_RNA, N_puzzle, N_eterna, N_constructs, N_datapoints) = get_rmdb_stats()

	return render_to_response(HTML_PATH['index'], {'N_all':N_all, 'N_RNA':N_RNA, 'N_constructs':N_constructs, 'N_datapoints':N_datapoints, 'news':news, 'entries':entries}, context_instance=RequestContext(request))

def browse(request):
	(N_all, N_RNA, N_puzzle, N_eterna, N_constructs, N_datapoints) = get_rmdb_stats()

	constructs_general = get_rmdb_category('general')
	constructs_puzzle = get_rmdb_category('puzzle')
	constructs_eterna = get_rmdb_category('eterna')

	return render_to_response(HTML_PATH['browse'], {'constructs_general':constructs_general, 'constructs_puzzle':constructs_puzzle, 'constructs_eterna':constructs_eterna, 'N_all':N_all, 'N_general':N_all-N_puzzle-N_eterna, 'N_puzzle':N_puzzle, 'N_eterna':N_eterna}, context_instance=RequestContext(request))


def specs(request, section):
	if len(section) > 0:
		return  HttpResponseRedirect('/repository/specs' + section)
	return render_to_response(HTML_PATH['specs'], {}, context_instance=RequestContext(request))

def tools(request):
	return render_to_response(HTML_PATH['repos'], {}, context_instance=RequestContext(request))

def license_mapseeker(request):
	return render_to_response(HTML_PATH['license_mapseeker'], {}, context_instance=RequestContext(request))

@login_required
def download_mapseeker(request):
	f = open(MEDIA_ROOT + "/code/mapseeker_user.csv", "a")
	f.write("%s," % time.strftime("%c"))
	request_usr = request.user
	f.write("%s,%s,%s %s," % (request_usr.username, request_usr.email, request_usr.first_name, request_usr.last_name))
	request_usr = User.objects.filter(username=request_usr.username)
	request_usr = RMDBUser.objects.filter(user=request_usr)
	f.write("%s - %s\n" %(request_usr.values('institution')[0]['institution'], request_usr.values('department')[0]['department']))
	f.close()
	return render_to_response(HTML_PATH['link_mapseeker'], {}, context_instance=RequestContext(request))

def tutorial_predict(request):
	return render_to_response(HTML_PATH['tt_predict'], {}, context_instance=RequestContext(request))

def tutorial_api(request):
	return render_to_response(HTML_PATH['tt_api'], {}, context_instance=RequestContext(request))

def tutorial_rdatkit(request):
	return render_to_response(HTML_PATH['tt_rdatkit'], {}, context_instance=RequestContext(request))

def tutorial_hitrace(request):
	return render_to_response(HTML_PATH['tt_hitrace'], {}, context_instance=RequestContext(request))

def tutorial_mapseeker(request):
	return render_to_response(HTML_PATH['tt_mapseeker'], {}, context_instance=RequestContext(request))

def about(request):
	(N_all, N_RNA, N_puzzle, N_eterna, N_constructs, N_datapoints) = get_rmdb_stats()
	return render_to_response(HTML_PATH['about'], {'N_all':N_all, 'N_RNA':N_RNA, 'N_constructs':N_constructs, 'N_datapoints':N_datapoints}, context_instance=RequestContext(request))

def license(request):
	return render_to_response(HTML_PATH['license'], {}, context_instance=RequestContext(request))

def history(request):
	all_log = get_history()
	return render_to_response(HTML_PATH['history'], {'hist': all_log}, context_instance=RequestContext(request))


def validate(request):
	flag = -1
	if request.method == 'POST':
		form = ValidateForm(request.POST, request.FILES)
		link = request.POST['link']
		uploadfile = ''
		if not link:
			try:
				uploadfile = request.FILES['file']
				(errors, messages, flag) = validate_file(uploadfile, link, request.POST['type'])
			except:
				pass
		else:
			(errors, messages, flag) = validate_file(uploadfile, link, request.POST['type'])

	if flag == -1:
		messages = []
		errors = []
		form = ValidateForm()
		flag = 0

	return render_to_response(HTML_PATH['validate'], {'form':form, 'valerrors':errors, 'valmsgs':messages, 'flag':flag}, context_instance=RequestContext(request))


def detail(request, rmdb_id):
	data_annotations_exist = False
	maxlen = 256
	maxlen_flag = False
	try:
		entry = RMDBEntry.objects.filter(rmdb_id=rmdb_id).order_by('-version')[0]
		comments = entry.comments.split('\n')
		entry.annotations = EntryAnnotation.objects.filter(section=entry)
		if entry.pdb_entries != None and len(entry.pdb_entries.strip()) > 0:
			entry.pdb_ids = [x.strip() for x in entry.pdb_entries.split(',')]
		else:
			entry.pdb_ids = []
		constructs = ConstructSection.objects.filter(entry=entry)
		for c in constructs:
			c.area_peaks_min, c.area_peaks_max, c.area_peaks, c.hist_data, c.precalc_structures  = get_plot_data(c.id, entry.type, maxlen)
			c.datas = DataSection.objects.filter(construct_section=c).order_by('id')
			#c.annotations = ConstructAnnotation.objects.filter(section=c)
			c.show_slideshow = entry.has_traces or entry.type in ['TT', 'SS']
			c.data_count = range(len(c.datas))
			if len(c.datas) > maxlen:
				c.datas = c.datas[:maxlen]
				maxlen_flag = True
			for d in c.datas:
				d.annotations = DataAnnotation.objects.filter(section=d).order_by('name')
				if d.annotations:
					data_annotations_exist = True
	except RMDBEntry.DoesNotExist:
		raise Http404
	
	return render_to_response(HTML_PATH['detail'], {'codebase':get_codebase(request), 'entry':entry, 'constructs':constructs, 'publication':entry.publication, 'comments':comments, 'data_annotations_exist':data_annotations_exist, 'maxlen_flag':maxlen_flag}, context_instance=RequestContext(request))


def predict(request):
	if request.method != 'POST':
		return render_to_response(HTML_PATH['predict'], {'secstr_form':PredictionForm(), 'rdatloaded':False, 'messages':[], 'other_errors':[]}, context_instance=RequestContext(request))
	else:
		try:
			sequences, titles, structures, modifiers, mapping_data, base_annotations, messages, valerrors = ([],[],[],[],[],[],[],[])

			is_get_rmdb = (len(request.POST['rmdbid']) > 0)
			is_get_file = (len(request.POST['rdatfile']) > 0)
			if is_get_rmdb or is_get_file:
				(messages, valerrors, bonuses_1d, bonuses_2d, titles, modifiers, offset_seqpos, temperature, sequences, refstruct) = parse_rdat_data(request, is_get_file)
				form = fill_predict_form(request, sequences, structures, temperature, refstruct, bonuses_1d, bonuses_2d, modifiers, titles, offset_seqpos)
				return render_to_response(HTML_PATH['predict'], {'secstr_form':form, 'rdatloaded':True, 'msg_y':messages, 'msg_r':valerrors})
			elif not request.POST['sequences']:
				return render_to_response(HTML_PATH['predict'], {'secstr_form':PredictionForm(), 'rdatloaded':False, 'msg_y':[], 'msg_r':[]})

			other_options = ' -t %s ' % (float(request.POST['temperature']) + 273.15)
			refstruct = SecondaryStructure(dbn=request.POST['refstruct'])

			lines = request.POST['sequences'].split('\n')
			for l in lines:
				if l:
					if l[0] == '>':
						titles.append(l.replace('>',''))
					else:
						if l.strip():
							sequences.append(rna.RNA(l.strip())) 
			if not sequences:
				messages.append('ERROR: No SEQUENCE found. Due to either no input field, or no modification lanes in RDAT.')
				return render_to_response(HTML_PATH['predict_res'], {'panels':[], 'messages':messages,'bppmimg':'', 'ncols':0, 'nrows':0}, context_instance=RequestContext(request))

			if 'structures' in request.POST:
				lines = request.POST['structures'].split('\n')
				for l in lines:
					if l.strip():
						structures.append(l)

			if request.POST['predtype'] in ('NN', '1D'):
				(base_annotations, structures, mapping_data, messages) = predict_run_1D_NN(request, sequences, mapping_data, structures, other_options, messages)

			if request.POST['predtype'] == '2D':
				(sequences, structures, messages, base_annotations) = predict_run_2D(request, sequences, titles, structures, other_options, messages)
				modifiers = ['']


			panels, ncols, nrows = render_to_varna([s.sequence for s in sequences], structures, modifiers, titles, mapping_data, base_annotations, refstruct)
			visform_params = {}
			visform_params['sequences'] = '\n'.join([s.sequence for s in sequences])
			visform_params['structures'] = '\n'.join([s.dbn for s in structures])
			if 'raw_bonuses' in request.POST:
				print [str(slope*log(1 + d) + intercept) for d in mapping_data[0].data()]
				visform_params['md_datas'] = '\n'.join([','.join([str(slope*log(1 + d) + intercept) for d in m.data()]) for m in mapping_data])
			else:
				visform_params['md_datas'] = '\n'.join([','.join([str(d) for d in m.data()]) for m in mapping_data])
			visform_params['md_seqposes'] = '\n'.join([','.join([str(pos) for pos in m.seqpos]) for m in mapping_data])
			visform_params['modifiers'] = modifiers
			visform_params['base_annotations'] = '\n'.join([bpdict_to_str(ann) for ann in base_annotations])
			visform_params['refstruct'] = refstruct.dbn
			visform = VisualizerForm(visform_params)
			return render_to_response(HTML_PATH['predict_res'], {'panels':panels, 'messages':messages,'ncols':ncols, 'nrows':nrows, 'form':visform}, context_instance=RequestContext(request))

		except IndexError, err:
			print err
			return render_to_response(HTML_PATH['predict'], {'secstr_form':PredictionForm(), 'rdatloaded':False, 'msg_y':messages, 'msg_r':['Invalid input. Please check your inputs and try again.']})


def search(request):
	sstring = request.GET['searchtext'].strip()
	entry_by_name = RMDBEntry.objects.filter(constructsection__name__icontains=sstring).filter(revision_status='PUB').order_by( 'rmdb_id', '-version' )
	entry_by_id = RMDBEntry.objects.filter(rmdb_id__icontains=sstring).filter(revision_status='PUB').order_by( 'rmdb_id', '-version' )
	entry_by_comment = RMDBEntry.objects.filter(comments__icontains=sstring).filter(revision_status='PUB').order_by( 'rmdb_id', '-version' )
	entry_by_desp = RMDBEntry.objects.filter(description__icontains=sstring).filter(revision_status='PUB').order_by( 'rmdb_id', '-version' )
	entry_by_data_anno = RMDBEntry.objects.filter(constructsection__datasection__dataannotation__value__icontains=sstring).filter(revision_status='PUB').order_by( 'rmdb_id', '-version' )
	entry_by_anno = RMDBEntry.objects.filter(entryannotation__value__icontains=sstring).filter(revision_status='PUB').order_by( 'rmdb_id', '-version' )
	entry_all = list(chain(entry_by_name, entry_by_id, entry_by_desp, entry_by_data_anno, entry_by_anno, entry_by_comment))
	
	entry_ids = []
	entries_general = []
	entries_eterna = []
	etypenames = dict(ENTRY_TYPE_CHOICES)

	for e in entry_all:
		if e.rmdb_id not in entry_ids:
			e.constructs = ConstructSection.objects.filter(entry=e).values('name').distinct()
			e.typename = etypenames[e.type]
			e.cid = ConstructSection.objects.filter(entry=e).values( 'id' )[ 0 ][ 'id' ]

			entry_ids.append(e.rmdb_id)
			if 'ETERNA' in e.rmdb_id:
				entries_eterna.append(e)
			else:
				entries_general.append(e)

	(N_all, _, _, _, _, _) = get_rmdb_stats()
	N_general = len(entries_general)
	N_eterna = len(entries_eterna)
	return render_to_response(HTML_PATH['search_res'], {'entries_general':entries_general, 'entries_eterna':entries_eterna, 'sstring':sstring, 'N_all':N_all, 'N_general':N_general, 'N_eterna':N_eterna}, context_instance=RequestContext(request))


def advanced_search(request):
	other_errors = []
	check_structure_balance = False
	valid = True
	if request.method == 'POST':
		try:
			form = AdvancedSearchForm(request.POST)
			constructs_byquery = {}
			rdat_paths = {}
			rdats = {}
			query_data = {}
			construct_secstructelemdicts = {}
			searchid = randint(1, 10000)
			if 'structure' in request.POST and 'sequence' in request.POST:
				if len(request.POST['structure']) != len(request.POST['sequence']) and len(request.POST['structure']) > 0 and len(request.POST['sequence']) > 0:
					other_errors.append('Structure and sequence motifs searched must have equal length')
					valid =  False
			try:
				numresults = int(request.POST['numresults'])
			except:
				valid =  False

			if valid:
				for field in ('structure', 'sequence'):
					if field in request.POST and request.POST[field]:
						if field == 'structure':
							if ' ' in request.POST[field]:
								check_structure_balance = True
							query_field = request.POST[field]
							for ec in '.(){}':
								query_field = query_field.replace(ec,'\\'+ec).replace('\\\\'+ec,ec)
							if check_structure_balance:
								query_field = query_field.replace(' ', '.*')
							constructs_byquery[field] = ConstructSection.objects.filter(structure__regex=query_field)
						if field =='sequence':
							query_field = ''.join([toIUPACregex(s.upper()) for s in request.POST[field]])
							constructs_byquery[field] = ConstructSection.objects.filter(sequence__regex=query_field)
						query_data[field] = query_field
				if 'secstructelems' in request.POST:
					query_data['secstructelems'] = request.POST.getlist('secstructelems')
					all_constructs = ConstructSection.objects.all()
					constructs_byquery['secstructelems'] = []
					cids = []
					for construct in all_constructs:
						if structure_is_valid(construct.structure):
							sstruct = SecondaryStructure(dbn=construct.structure)
							ssdict = sstruct.explode()
							for elem in query_data['secstructelems']:
								if elem in ssdict and ssdict[elem]:
									cids.append(construct.id)
									construct_secstructelemdicts[construct.id] = ssdict
									break
							constructs_byquery['secstructelems'] = ConstructSection.objects.filter(id__in=cids)
				if len(query_data) == 0: # No search criteria was chosen, get all constructs
					constructs_byquery['all'] = ConstructSection.objects.all()
					query_data['all'] = True

				if 'background_processed' in request.POST:
					bp_entry_ids = [d.section.rmdb_id for d in EntryAnnotation.objects.filter(name='processing', value='backgroundSubtraction')]
				for field in constructs_byquery:
					entry_types = request.POST.getlist('entry_type')
					modifiers = request.POST.getlist('modifiers')
					constructs_byquery[field].exclude(entry__latest=False)
					for t, name in ENTRY_TYPE_CHOICES:
						if t not in entry_types:
							constructs_byquery[field] = constructs_byquery[field].exclude(entry__type=t)
					for t, name in MODIFIERS:
						if t not in modifiers:
							constructs_byquery[field] = constructs_byquery[field].exclude(entry__rmdb_id__contains='_%s_' % t)
					if 'include_eterna' not in request.POST:
						constructs_byquery[field] = constructs_byquery[field].exclude(entry__from_eterna=True)
					if 'background_processed' in request.POST:
						constructs_byquery[field] = constructs_byquery[field].filter(entry__rmdb_id__in=bp_entry_ids)

				constructs = constructs_byquery.values()[0]
				for k, v in constructs_byquery.iteritems():
					constructs = [c for c in constructs if c in v]

				entries_visited = []
				unique_constructs = []
				for c in constructs:
					if c.entry.rmdb_id not in entries_visited:
						unique_constructs.append(c)
						entries_visited.append(c.entry.rmdb_id)
				rdat, all_values, cell_labels, values_min, values_max, values_min_heatmap, values_max_heatmap, unpaired_bins, paired_bins, unpaired_bin_anchors, paired_bin_anchors, rmdb_ids, messages, numallresults, render = get_restricted_RDATFile_and_plot_data(unique_constructs, numresults, query_data, searchid, construct_secstructelemdicts, check_structure_balance)
				
				rdat_path = '/search/%s.rdat' % searchid
				rdat.save(RDAT_FILE_DIR + rdat_path, version=0.24)

				return render_to_response(HTML_PATH['adv_search_res'], \
						{'rdat_path':rdat_path, 'all_values':simplejson.dumps(all_values), 'values_min':values_min, 'values_max':values_max, \
						'values_min_heatmap':values_min_heatmap, 'values_max_heatmap':values_max_heatmap, \
						'rmdb_ids':simplejson.dumps(rmdb_ids), 'messages':messages, \
						'unpaired_bins':simplejson.dumps(unpaired_bins), 'paired_bins':simplejson.dumps(paired_bins), \
						'unpaired_bin_anchors':simplejson.dumps(unpaired_bin_anchors), 'paired_bin_anchors':simplejson.dumps(paired_bin_anchors), \
						'render':render, 'render_paired_histogram':len(paired_bins) > 0, 'render_unpaired_histogram':len(unpaired_bins) > 0,\
						'form':form, 'numresults':numallresults, 'cell_labels':simplejson.dumps(cell_labels), 'all_results_rendered':numallresults <= numresults},\
						context_instance=RequestContext(request) )

		except ValueError as e:
			return render_to_response(HTML_PATH['adv_search_res'], {'render':False}, context_instance=RequestContext(request))

	else:
		form = AdvancedSearchForm()
	return render_to_response(HTML_PATH['adv_search'], {'form':form, 'other_errors':other_errors}, context_instance=RequestContext(request))


@login_required
def upload(request):
	error_msg = []
	flag = 0
	entry = []
	if request.method == 'POST':
		try:
			form = UploadForm(request.POST, request.FILES)
			if form.is_valid():
				proceed = True
				if not check_rmdb_id(form.cleaned_data['rmdb_id']):
					error_msg.append('RMDB ID invalid. Hover mouse over the field to see instructions.')
					flag = 1
					proceed = False
				else:
					isatabfile = ISATABFile()
					isatabfile.loaded = False
					rdatfile = RDATFile()
					rdatfile.loaded = False

					uploadfile = request.FILES['file']
					rf = write_temp_file(uploadfile)

					if form.cleaned_data['filetype'] == 'isatab':
						try:
							isatabfile.load(rf.name)
							isatabfile.loaded = True
							rdatfile = isatabfile.toRDAT()
						except Exception:
							error_msg.append('ISATAB file invalid; please check and resubmit.')
							flag = 1
							proceed = False
					else:
						try:
							rdatfile.load(rf)
							rdatfile.loaded = True
							isatabfile = rdatfile.toISATAB()
						except Exception:
							error_msg.append('RDAT file invalid; please check and resubmit.')
							flag = 1
							proceed = False

				if proceed:
					(error_msg, entry) = submit_rmdb_entry(form, request, rdatfile, isatabfile)
					flag = 2
			else:
				flag = 1
				if 'rmdb_id' in form.errors: error_msg.append('RMDB_ID field is required.')
				if 'file' in form.errors: error_msg.append('Input file field is required.')
				if 'authors' in form.errors: error_msg.append('Authors field is required.')

		except IndexError:
			flag = 1
			error_msg.append('Input file invalid; please check and resubmit.')
	else:
		form = UploadForm()
	return render_to_response(HTML_PATH['upload'], {'form':form, 'error_msg':error_msg, 'flag':flag, 'entry':entry}, context_instance=RequestContext(request))


def user_login(request):
	if request.method == 'POST':
		username = request.POST['username']
		password = request.POST['password']
		user = authenticate(username=username, password=password)

		if user is not None:
			if user.is_active:
				login(request, user)
				next = request.META.get('HTTP_REFERER','/').replace("?login=1", "")
				if "?login=0" in next:
					next = "/repository/deposit/submit/"
				if "?login=-1" in next:
					next = "/repository/analyze/tools/mapseeker/download/"
				return HttpResponseRedirect(next)
			else:
				messages.error(request, 'Inactive/disabled account. Please contact us.')
		else:
			messages.error(request, 'Invalid username and/or password. Please try again.')
		
		return redirect('/')


def register(request):
	error_msg = []
	flag = 0
	if request.method == 'POST':
		form = RegistrationForm(request.POST)
		if form.is_valid():
			error_msg = check_login_register(form)

			if not error_msg:
				try:
					user =  User.objects.create_user(form.cleaned_data['username'], form.cleaned_data['email'], form.cleaned_data['password'])
					user.first_name = form.cleaned_data['firstname']
					user.last_name = form.cleaned_data['lastname']
					user.set_password(form.cleaned_data['password'])
					user.is_active = True
					user.save()

					rmdbuser = RMDBUser()
					rmdbuser.user = user
					rmdbuser.institution = form.cleaned_data['institution']
					rmdbuser.department = form.cleaned_data['department']
					rmdbuser.save()

					flag = 1
				except:
					error_msg.append('Username already exists. Try another.')
				# authuser = authenticate(username=user.username, password=form.cleaned_data['password'])
				# login(request, authuser)
				# return HttpResponseRedirect('/repository/')
		else:
			if 'username' in form.errors: error_msg.append('Username field is required.')
			if 'password' in form.errors: error_msg.append('Password field is required.')
			if 'firstname' in form.errors: error_msg.append('First name field is required.')
			if 'lastname' in form.errors: error_msg.append('Last name field is required.')
			if 'institution' in form.errors: error_msg.append('Institution field is required.')
			if 'department' in form.errors: error_msg.append('Department field is required.')
			if 'email' in form.errors: error_msg.append('Email field is required.')
			error_msg.append('Form invalid: missing required field(s).')
	else:
		form = RegistrationForm()

	return render_to_response(HTML_PATH['register'], {'reg_form':form, 'error_msg':error_msg, 'flag':flag})


def user_logout(request):
	logout(request)
	return HttpResponseRedirect("/repository/")

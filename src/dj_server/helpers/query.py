import datajoint as dj
import json
import os
import numpy as np
import datetime
import base64
from io import BytesIO
from tqdm import tqdm
import h5py
from matplotlib.figure import Figure

# Import shared data from retinanalysis instead of local utils
from retinanalysis.utils import DATA_DIR as NAS_DATA_DIR, ANALYSIS_DIR as NAS_ANALYSIS_DIR
from retinanalysis.utils.database_pop import (
    table_arr, make_table_dict, child_table, parent_table, fields
)

Experiment: dj.Manual = None
Animal: dj.Manual = None
Preparation: dj.Manual = None
Cell: dj.Manual = None
EpochGroup: dj.Manual = None
EpochBlock: dj.Manual = None
Epoch: dj.Manual = None
Response: dj.Manual = None
Stimulus: dj.Manual = None
Protocol: dj.Manual = None
Tags: dj.Manual = None

db: dj.VirtualModule = None
table_dict: dict = None
user: str = None
query: dj.expression.QueryExpression = None

def fill_tables(username: str, db_param: dj.VirtualModule):
    global db, user
    if not db or not user:
        user = username
        db = db_param
    global Experiment, Animal, Preparation, Cell, EpochGroup, EpochBlock, Epoch, Response, Stimulus, Protocol, Tags
    global table_dict
    Experiment = db.Experiment
    Animal = db.Animal
    Preparation = db.Preparation
    Cell = db.Cell
    EpochGroup = db.EpochGroup
    EpochBlock = db.EpochBlock
    Epoch = db.Epoch
    Response = db.Response
    Stimulus = db.Stimulus
    Protocol = db.Protocol
    Tags = db.Tags
    table_dict = make_table_dict(Experiment, Animal, Preparation, Cell, EpochGroup,
                                  EpochBlock, Epoch, Response, Stimulus, Tags)

# ============================================================
# Browse functions (new — metadata-only, fast)
# ============================================================

def get_experiment_list(db_param: dj.VirtualModule) -> list:
    """Return lightweight experiment metadata (patch / single-cell only)."""
    experiments = (db_param.Experiment & 'is_mea=0').fetch(as_dict=True)
    result = []
    for exp in experiments:
        result.append({
            'id': exp['id'],
            'exp_name': exp['exp_name'],
            'label': exp.get('label', ''),
            'date_added': str(exp.get('date_added', '')),
            'start_time': str(exp.get('start_time', '')),
            'experimenter': exp.get('experimenter', ''),
            'rig': exp.get('rig', ''),
        })
    return result

def get_experiment_tree(experiment_id: int, db_param: dj.VirtualModule) -> dict:
    """Build hierarchical metadata tree for one experiment (no .h5 access).

    Returns: experiment -> animals -> preparations -> cells -> epoch_groups -> epoch_blocks
    Each node has label, id, protocol (if applicable), and count of children.
    Epochs and below are NOT loaded — those are fetched on demand.
    """
    exp = (db_param.Experiment & f"id={experiment_id}").fetch1()
    tree = {
        'id': exp['id'], 'level': 'experiment',
        'label': exp['label'], 'exp_name': exp['exp_name'],
        'experimenter': exp.get('experimenter', ''),
        'start_time': str(exp.get('start_time', '')),
    }

    # Walk: Animal -> Preparation -> Cell -> EpochGroup -> EpochBlock
    # Stop before Epoch (those require on-demand loading)
    levels = ['animal', 'preparation', 'cell', 'epoch_group', 'epoch_block']
    table_map = {
        'animal': db_param.Animal,
        'preparation': db_param.Preparation,
        'cell': db_param.Cell,
        'epoch_group': db_param.EpochGroup,
        'epoch_block': db_param.EpochBlock,
    }

    def build_subtree(parent_id, level_idx):
        if level_idx >= len(levels):
            return []
        level_name = levels[level_idx]
        tbl = table_map[level_name]
        rows = (tbl & f"parent_id={parent_id}").fetch(as_dict=True)
        children = []
        for row in rows:
            node = {
                'id': row['id'], 'level': level_name,
                'label': row.get('label', ''),
                'experiment_id': row.get('experiment_id', experiment_id),
            }
            # Add protocol name for epoch_group and epoch_block
            if level_name in ('epoch_group', 'epoch_block') and 'protocol_id' in row:
                try:
                    proto = (db_param.Protocol & f"protocol_id={row['protocol_id']}").fetch1('name')
                    node['protocol'] = proto
                except:
                    node['protocol'] = ''
            # Count children at next level for lazy loading indicator
            if level_idx + 1 < len(levels):
                next_tbl = table_map[levels[level_idx + 1]]
                node['child_count'] = len(next_tbl & f"parent_id={row['id']}")
                node['children'] = build_subtree(row['id'], level_idx + 1)
            elif level_name == 'epoch_block':
                # Count epochs for on-demand loading
                node['epoch_count'] = len(db_param.Epoch & f"parent_id={row['id']}")
                node['children'] = []  # epochs loaded on demand
            children.append(node)
        return children

    tree['children'] = build_subtree(experiment_id, 0)
    return tree

def get_on_demand_data(level: str, item_id: int, db_param: dj.VirtualModule) -> dict:
    """Fetch epoch-level data including responses/stimuli from .h5 on demand."""
    if level == 'epoch_block':
        # Return epochs for this block (metadata only, still no .h5)
        epochs = (db_param.Epoch & f"parent_id={item_id}").fetch(as_dict=True)
        result = []
        for ep in epochs:
            node = {
                'id': ep['id'], 'level': 'epoch',
                'label': ep.get('label', ''),
                'experiment_id': ep.get('experiment_id'),
                'start_time': str(ep.get('start_time', '')),
                'end_time': str(ep.get('end_time', '')),
            }
            # Count responses/stimuli
            node['response_count'] = len(db_param.Response & f"parent_id={ep['id']}")
            node['stimulus_count'] = len(db_param.Stimulus & f"parent_id={ep['id']}")
            result.append(node)
        return {'epochs': result}
    elif level == 'epoch':
        # Return response/stimulus metadata for this epoch
        responses = (db_param.Response & f"parent_id={item_id}").fetch(as_dict=True)
        stimuli = (db_param.Stimulus & f"parent_id={item_id}").fetch(as_dict=True)
        return {
            'responses': [
                {'id': r['id'], 'device_name': r['device_name'],
                 'h5path': r['h5path'], 'label': r.get('label', ''),
                 'sample_rate': r.get('sample_rate', '')}
                for r in responses
            ],
            'stimuli': [
                {'id': s['id'], 'device_name': s['device_name'],
                 'h5path': s['h5path']}
                for s in stimuli
            ],
        }
    return {}

# ============================================================
# Existing query functions (kept for complex query builder)
# ============================================================

def query_levels():
    return table_arr

def table_fields(table_name: str, username: str, db_param: dj.VirtualModule) -> list:
    if not table_dict:
        fill_tables(username, db_param)
    table: dj.Manual = table_dict[table_name] if table_name in table_dict.keys() else None
    if not table:
        return None
    tuples = []
    for field in table.heading.attributes.keys():
        if table.heading.attributes[field].type == 'timestamp':
            tuples.append((field, 'date'))
        elif table.heading.attributes[field].json:
            tuples.append((field, 'json'))
        elif table.heading.attributes[field].string:
            tuples.append((field, 'string'))
        elif table.heading.attributes[field].numeric:
            tuples.append((field, 'numeric'))
        else:
            print(f"Unknown type for field {field}")
            return None
    if table_name in ['epoch_block', 'epoch_group']:
        tuples.append(('protocol_name', 'string'))
    return tuples

def saved_queries(download_dir: str) -> dict:
    if not os.path.exists(os.path.join(download_dir, 'query.json')):
        return {}
    with open(os.path.join(download_dir, 'query.json'), 'r') as f:
        queries = json.load(f)
        return queries

def add_query(query_name: str, query_obj: dict, download_dir: str):
    queries = saved_queries(download_dir)
    queries[query_name] = query_obj
    with open(os.path.join(download_dir, 'query.json'), 'w') as f:
        json.dump(queries, f)

def delete_query(query_name: str, download_dir: str):
    queries = saved_queries(download_dir)
    if query_name in queries.keys():
        queries.pop(query_name)
    with open(os.path.join(download_dir, 'query.json'), 'w') as f:
        json.dump(queries, f)

def process_condition(table_name: str, cond: dict):
    if cond['type'] == 'TAG':
        tag_ids = (Tags & f'table_name="{table_name}"' & cond['value']).fetch('table_id')
        if len(tag_ids) == 0:
            return 'FALSE'
        return f'id in ({",".join(str(i) for i in tag_ids)})'
    else:
        return cond['value']

def apply_conditions(conds: dict, table_name: str) -> list:
    cur_cond = []
    if not conds:
        return cur_cond
    type = list(conds.keys())[0]
    if type == 'COND':
        cur_cond.append(process_condition(table_name, conds['COND']))
        return cur_cond
    for entry in conds[type]:
        cur_cond.extend(apply_conditions(entry, table_name))
    if type == 'AND' or type == 'NOT':
        cur_cond = dj.AndList(cur_cond)
        if type == 'NOT':
            cur_cond = [dj.Not(cur_cond)]
    return cur_cond

def process_query(query_obj: dict) -> dj.expression.QueryExpression:
    query = Experiment
    for table in table_arr[:-2]:
        if table in query_obj.keys():
            if table in ['epoch_group', 'epoch_block']:
                query = query * Protocol.proj(protocol_name='name')
                if query_obj[table]:
                    query = query & apply_conditions(query_obj[table], table)
                query = query.proj(**{f'{table}_protocol_id': 'protocol_id'})
            else:
                if query_obj[table]:
                    query = query & apply_conditions(query_obj[table], table)
        query = query.proj(**{f'{table}_id':'id'}) * table_dict[child_table(table)].proj(**{f'{table}_id':'parent_id'})
    return query.proj(response_id='id')

def create_query(query_obj: dict, username: str, db_param: dj.VirtualModule) -> dj.expression.QueryExpression:
    global query
    fill_tables(username, db_param)
    if not db:
        return False
    query = process_query(query_obj)
    return query

def generate_tree(query: dj.expression.QueryExpression,
                  exclude_levels: list,
                  include_meta: bool = False,
                  cur_level: int = 0) -> list:
    if cur_level == 7:
        return []
    children = []
    if cur_level == 0:
        iter_obj = tqdm(np.unique(query.fetch(f'{table_arr[cur_level]}_id')))
    else:
        iter_obj = np.unique(query.fetch(f'{table_arr[cur_level]}_id'))
    for entry in iter_obj:
        if table_arr[cur_level] in exclude_levels:
            children.extend(generate_tree(query & f"{table_arr[cur_level]}_id={entry}",
                                          exclude_levels, include_meta, cur_level + 1))
        else:
            child = {}
            obj = ((table_dict[table_arr[cur_level]] & f"id={entry}"
                    ).fetch(as_dict=True) if table_arr[cur_level] != 'epoch_group' and table_arr[cur_level] != 'epoch_block' else (
                        (table_dict[table_arr[cur_level]] & f"id={entry}") * Protocol.proj(protocol_name='name')
                    ).fetch(as_dict=True))[0]
            child['level'] = table_arr[cur_level]
            child['id'] = obj['id']
            if child['level'] != 'experiment':
                child['experiment_id'] = obj['experiment_id']
            if 'label' in obj.keys():
                child['label'] = obj['label']
            if 'protocol_name' in obj.keys():
                child['protocol'] = obj['protocol_name']
            if include_meta:
                child['object'] = (table_dict[table_arr[cur_level]] & f"id={entry}"
                                  ).fetch(as_dict=True) if table_arr[cur_level] != 'epoch_group' and table_arr[cur_level] != 'epoch_block' else (
                                      (table_dict[table_arr[cur_level]] & f"id={entry}") * Protocol.proj(protocol_name='name')).fetch(as_dict=True)
            child['tags'] = (Tags & f'table_name="{table_arr[cur_level]}"' & f'table_id={entry}').proj('user', 'tag').fetch(as_dict=True)
            if table_arr[cur_level] == 'epoch':
                child['children'] = []
                if include_meta:
                    child['responses'] = (Response & f'parent_id={entry}').fetch(as_dict=True)
                    child['stimuli'] = (Stimulus & f'parent_id={entry}').fetch(as_dict=True)
            else:
                child['children'] = generate_tree(
                    query & f"{table_arr[cur_level]}_id={entry}",
                    exclude_levels, include_meta, cur_level + 1)
            children.append(child)
    return children

def generate_object_tree(query: dj.expression.QueryExpression,
                         exclude_levels: list,
                         cur_level: int = 0) -> list:
    if cur_level == 7:
        return []
    children = []
    for entry in np.unique(query.fetch(f'{table_arr[cur_level]}_id')):
        if table_arr[cur_level] in exclude_levels:
            children.extend(generate_object_tree(query & f"{table_arr[cur_level]}_id={entry}", exclude_levels, cur_level + 1))
        else:
            child = {}
            obj = ((table_dict[table_arr[cur_level]] & f"id={entry}"
                    ).fetch(as_dict=True) if table_arr[cur_level] != 'epoch_group' and table_arr[cur_level] != 'epoch_block' else (
                        (table_dict[table_arr[cur_level]] & f"id={entry}") * Protocol.proj(protocol_name='name')
                    ).fetch(as_dict=True))[0]
            child['level'] = table_arr[cur_level]
            child['id'] = obj['id']
            if child['level'] != 'experiment':
                child['experiment_id'] = obj['experiment_id']
            if 'label' in obj.keys():
                child['label'] = obj['label']
            if 'protocol_name' in obj.keys():
                child['protocol'] = obj['protocol_name']
            child['object'] = (table_dict[table_arr[cur_level]] & f"id={entry}"
                              ).fetch(as_dict=True) if table_arr[cur_level] != 'epoch_group' and table_arr[cur_level] != 'epoch_block' else (
                                  (table_dict[table_arr[cur_level]] & f"id={entry}") * Protocol.proj(protocol_name='name')).fetch(as_dict=True)
            child['tags'] = (Tags & f'table_name="{table_arr[cur_level]}"' & f'table_id={entry}').proj('user', 'tag').fetch(as_dict=True)
            if table_arr[cur_level] == 'epoch':
                child['children'] = []
                child['responses'] = (Response & f'parent_id={entry}').fetch(as_dict=True)
                child['stimuli'] = (Stimulus & f'parent_id={entry}').fetch(as_dict=True)
            else:
                child['children'] = generate_object_tree(query & f"{table_arr[cur_level]}_id={entry}", exclude_levels, cur_level + 1)
            children.append(child)
    return children

# Results/visualization helpers

def get_metadata_helper(level: str, id: int) -> dict:
    return (table_dict[level] & f"id={id}").fetch1()

def get_options(level: str, id: int, experiment_id: int) -> dict:
    if level == 'epoch':
        h5_file = (Experiment & f'id={experiment_id}').fetch1('data_file')
        responses = []
        for item in (Response & f'parent_id={id}').fetch(as_dict=True):
            responses.append({'label': item['device_name'],
                              'h5_path': item['h5path'],
                              'h5_file': h5_file,
                              'vis_type': 'epoch-singlecell'})
        stimuli = []
        for item in (Stimulus & f'parent_id={id}').fetch(as_dict=True):
            stimuli.append({'label': item['device_name'],
                            'h5_path': item['h5path'],
                            'h5_file': h5_file,
                            'vis_type': 'epoch-singlecell'})
        return {'responses': responses, 'stimuli': stimuli}
    return None

def get_data_generic(table_name: str, id: int):
    if table_name == 'Stimulus' or table_name == 'Response':
        h5_file = (Experiment & (
                        Epoch & (
                            table_dict[table_name] & f'id={id}').fetch1('parent_id')
                        ).fetch1('experiment_id')
                    ).fetch1('data_file')
    else:
        h5_file = (Experiment & (
                        table_dict[table_name] & f'id={id}').fetch1('experiment_id')
                    ).fetch1('data_file')
    h5_path = (table_dict[table_name] & f'id={id}').fetch1('h5path')
    with h5py.File(h5_file, 'r') as f:
        return f[h5_path]['data']['quantity']

def get_trace_binary(h5_file: str, h5_path: str) -> bytes:
    with h5py.File(h5_file, 'r') as f:
        fig = Figure()
        ax = fig.subplots()
        if 'data' not in f[h5_path].keys():
            return None
        ax.plot(f[h5_path]['data']['quantity'])
        buf = BytesIO()
        fig.savefig(buf, format='png')
        data = base64.b64encode(buf.getbuffer()).decode("ascii")
    return data

# Tag operations

def add_tags(ids: list, tag: str):
    rows = []
    for id in ids:
        experiment_id, table_name, table_id = id.split('-')
        rows.append({'h5_uuid': (table_dict[table_name] & f"id={table_id}").fetch1()['h5_uuid'],
                     'experiment_id': experiment_id,
                     'table_name': table_name,
                     'table_id': table_id,
                     'user': user,
                     'tag': tag})
    Tags.insert(rows)

def delete_tags(ids: list, tag: str):
    for id in ids:
        experiment_id, table_name, table_id = id.split('-')
        (Tags & f"experiment_id='{experiment_id}'" & f"table_name='{table_name}'" & f"table_id={table_id}"
         & f"tag='{tag}'").delete(prompt=False)

def build_tags_dict(cur_id: int, cur_level: int, user: str, old_dict: dict) -> dict:
    cur_dict = {}
    tags = []
    if old_dict and 'tags' in old_dict.keys():
        for index in range(len(old_dict['tags'])):
            u, t = old_dict['tags'][index]
            if u != user:
                tags.append((u, t))
    table_name = table_arr[cur_level]
    if len(Tags & f"table_name='{table_name}'" & f"table_id={cur_id}" & f"user='{user}'") > 0:
        for tag in (Tags & f"table_name='{table_name}'" & f"table_id={cur_id}" & f"user='{user}'").fetch('tag'):
            tags.append((user, tag))
    if len(tags) > 0:
        cur_dict['tags'] = tags
    if table_name != 'epoch':
        children = (table_dict[table_arr[cur_level+1]] & f"parent_id={cur_id}").fetch()
        for child_row in children:
            cur_dict[child_row['h5_uuid']] = build_tags_dict(child_row['id'], cur_level+1, user,
                                                              old_dict[child_row['h5_uuid']] if old_dict else None)
    return cur_dict

def push_tags(experiment_ids: list):
    for experiment_id in experiment_ids:
        tags_file = (Experiment & f"id={experiment_id}").fetch1('tags_file')
        h5_uuid = (Experiment & f"id={experiment_id}").fetch1('h5_uuid')
        with open(tags_file, 'r') as f:
            old_dict = json.load(f)
        cur_dict = {}
        cur_dict[h5_uuid] = build_tags_dict(experiment_id, 0, user, old_dict[h5_uuid] if old_dict else None)
        with open(tags_file, 'w') as f:
            json.dump(cur_dict, f)

def append_tags(h5_uuid: str, experiment_id: int, table_name: str, table_id: int, user_skip: str, tags_dict: dict):
    if tags_dict and h5_uuid in tags_dict.keys() and 'tags' in tags_dict[h5_uuid].keys():
        for u, tag in tags_dict[h5_uuid]['tags']:
            if user_skip and u == user_skip:
                continue
            Tags.insert1({
                'h5_uuid': h5_uuid,
                'experiment_id': experiment_id,
                'table_name': table_name,
                'table_id': table_id,
                'user': u,
                'tag': tag
            })
        return tags_dict[h5_uuid]
    return None

def traverse_and_append_tags(experiment_id: int, parent_id: int, cur_level: int, user_skip: str, tags_dict: dict):
    table_name = table_arr[cur_level]
    if table_name == 'response' or table_name == 'stimulus':
        return
    if table_name == 'experiment':
        ids = (table_dict[table_name] & f"id={experiment_id}").fetch('id')
    else:
        ids = (table_dict[table_name] & f"parent_id={parent_id}").fetch('id')
    for id in ids:
        h5_uuid = (table_dict[table_name] & f"id={id}").fetch1('h5_uuid')
        traverse_and_append_tags(experiment_id, id, cur_level + 1, user_skip,
                                 append_tags(h5_uuid, experiment_id, table_name,
                                             id, user_skip, tags_dict))

def pull_tags(experiment_ids: list):
    for experiment_id in experiment_ids:
        (Tags & f"experiment_id='{experiment_id}'" & f"user!='{user}'").delete(prompt=False)
        tags_file = (Experiment & f"id={experiment_id}").fetch1('tags_file')
        with open(tags_file, 'r') as f:
            tags = json.load(f)
        if tags == {}:
            continue
        traverse_and_append_tags(experiment_id, experiment_id, 0, user, tags)

def reset_tags(experiment_ids: list):
    for experiment_id in experiment_ids:
        (Tags & f"experiment_id='{experiment_id}'").delete(prompt=False)
        tags_file = (Experiment & f"id={experiment_id}").fetch1('tags_file')
        with open(tags_file, 'r') as f:
            tags = json.load(f)
        if tags == {}:
            continue
        traverse_and_append_tags(experiment_id, experiment_id, 0, None, tags)

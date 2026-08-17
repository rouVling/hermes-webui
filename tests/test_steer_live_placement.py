"""Live Steer placement: park at send, split the turn after the consume boundary.

The current indicator is appended to #msgInner after #liveAssistantTurn, so the
live turn keeps growing above it and the Steer stays glued above the composer.
Users cannot tell when the model crossed the tool-result boundary where the
agent injects pending steer.

These tests drive the real helpers from static/commands.js and static/ui.js
with a jsdom-free DOM shim (same approach as test_issue4658). They assert
observable node order, not source strings of the fix.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from tests.helpers import source_between

REPO = Path(__file__).parent.parent
COMMANDS_JS = (REPO / "static" / "commands.js").read_text(encoding="utf-8")
MESSAGES_JS = (REPO / "static" / "messages.js").read_text(encoding="utf-8")
UI_JS = (REPO / "static" / "ui.js").read_text(encoding="utf-8")
STYLE_CSS = (REPO / "static" / "style.css").read_text(encoding="utf-8")

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not on PATH")


def _steer_indicator_src() -> str:
    return source_between(
        COMMANDS_JS,
        "function _steerIndicatorHost(",
        "\nfunction _showSteerRecovery(",
    )


_DOM_SHIM = r"""
function makeEl(tag){
  const el = {
    tagName: String(tag||'div').toUpperCase(),
    nodeType: 1,
    id: '',
    className: '',
    textContent: '',
    children: [],
    parentNode: null,
    parentElement: null,
    _attrs: {},
    dataset: {},
    style: {},
    hidden: false,
    isConnected: true,
    classList: {
      add(...cs){ cs.forEach(c=>{ if(!c) return; const set=new Set((el.className||'').split(/\s+/).filter(Boolean)); set.add(c); el.className=[...set].join(' '); }); },
      remove(...cs){ cs.forEach(c=>{ const set=new Set((el.className||'').split(/\s+/).filter(Boolean)); set.delete(c); el.className=[...set].join(' '); }); },
      contains(c){ return new Set((el.className||'').split(/\s+/).filter(Boolean)).has(c); },
      toggle(c, on){ const want=on===undefined?!el.classList.contains(c):!!on; if(want) el.classList.add(c); else el.classList.remove(c); return want; },
    },
    setAttribute(k,v){
      const key=String(k);
      const val=String(v);
      el._attrs[key]=val;
      if(key==='id') el.id=val;
      if(key==='class') el.className=val;
      if(key.startsWith('data-')){
        const dk=key.slice(5).replace(/-([a-z])/g,(_,ch)=>ch.toUpperCase());
        el.dataset[dk]=val;
      }
    },
    getAttribute(k){
      const key=String(k);
      if(key==='id') return el.id||null;
      if(key==='class') return el.className||null;
      return Object.prototype.hasOwnProperty.call(el._attrs,key)?el._attrs[key]:null;
    },
    hasAttribute(k){ return el.getAttribute(k)!=null; },
    removeAttribute(k){
      const key=String(k);
      delete el._attrs[key];
      if(key==='id') el.id='';
      if(key.startsWith('data-')){
        const dk=key.slice(5).replace(/-([a-z])/g,(_,ch)=>ch.toUpperCase());
        delete el.dataset[dk];
      }
    },
    appendChild(child){
      if(child.parentNode) child.parentNode.removeChild(child);
      el.children.push(child);
      child.parentNode=el;
      child.parentElement=el;
      return child;
    },
    insertBefore(child, ref){
      if(!ref) return el.appendChild(child);
      if(child.parentNode) child.parentNode.removeChild(child);
      const i=el.children.indexOf(ref);
      if(i<0) return el.appendChild(child);
      el.children.splice(i,0,child);
      child.parentNode=el;
      child.parentElement=el;
      return child;
    },
    insertAdjacentElement(where, child){
      if(where==='afterend'){
        if(!el.parentNode) return child;
        const next=el.nextSibling;
        if(next) el.parentNode.insertBefore(child, next);
        else el.parentNode.appendChild(child);
        return child;
      }
      if(where==='beforebegin'){
        if(!el.parentNode) return child;
        el.parentNode.insertBefore(child, el);
        return child;
      }
      throw new Error('insertAdjacentElement '+where);
    },
    removeChild(child){
      const i=el.children.indexOf(child);
      if(i>=0) el.children.splice(i,1);
      child.parentNode=null;
      child.parentElement=null;
      return child;
    },
    remove(){ if(el.parentNode) el.parentNode.removeChild(el); },
    matches(sel){ return _match(el, sel); },
    querySelector(sel){ return _find(el, sel, false); },
    querySelectorAll(sel){ return _findAll(el, sel); },
    get firstElementChild(){ return el.children[0]||null; },
    get lastElementChild(){ return el.children.length?el.children[el.children.length-1]:null; },
    get nextSibling(){
      if(!el.parentNode) return null;
      const sibs=el.parentNode.children;
      const i=sibs.indexOf(el);
      return i>=0&&i+1<sibs.length?sibs[i+1]:null;
    },
    get nextElementSibling(){ return el.nextSibling; },
    get previousElementSibling(){
      if(!el.parentNode) return null;
      const sibs=el.parentNode.children;
      const i=sibs.indexOf(el);
      return i>0?sibs[i-1]:null;
    },
    compareDocumentPosition(other){
      if(other===el) return 0;
      const DOCUMENT_POSITION_FOLLOWING=4;
      const DOCUMENT_POSITION_PRECEDING=2;
      const DOCUMENT_POSITION_CONTAINED_BY=16;
      const DOCUMENT_POSITION_CONTAINS=8;
      if(_contains(el, other)) return DOCUMENT_POSITION_CONTAINED_BY | DOCUMENT_POSITION_FOLLOWING;
      if(_contains(other, el)) return DOCUMENT_POSITION_CONTAINS | DOCUMENT_POSITION_PRECEDING;
      const a=_path(el), b=_path(other);
      const n=Math.min(a.length,b.length);
      let i=0;
      while(i<n&&a[i]===b[i]) i++;
      if(i===0) return DOCUMENT_POSITION_FOLLOWING;
      const parent=a[i-1];
      const ai=parent.children.indexOf(a[i]||el);
      const bi=parent.children.indexOf(b[i]||other);
      return ai<bi?DOCUMENT_POSITION_FOLLOWING:DOCUMENT_POSITION_PRECEDING;
    },
  };
  return el;
}
function _contains(root, node){
  let cur=node;
  while(cur){
    if(cur===root) return cur!==node?true:false;
    cur=cur.parentNode;
  }
  return false;
}
function _path(node){
  const out=[];
  let cur=node;
  while(cur){ out.unshift(cur); cur=cur.parentNode; }
  return out;
}
function _matchOne(el, raw){
  const sel=String(raw||'').trim();
  if(!sel) return false;
  if(sel==='*') return true;
  let rest=sel;
  if(rest[0]==='#'){
    const id=rest.slice(1).split(/[.\[]/)[0];
    if(el.id!==id) return false;
    rest=rest.slice(1+id.length);
  }else if(/^[a-zA-Z]/.test(rest)){
    const tag=rest.match(/^[a-zA-Z][\w-]*/);
    if(tag && el.tagName!==tag[0].toUpperCase()) return false;
    rest=rest.slice(tag[0].length);
  }
  while(rest){
    if(rest[0]==='.'){
      const cls=rest.slice(1).match(/^[\w-]+/);
      if(!cls || !el.classList.contains(cls[0])) return false;
      rest=rest.slice(1+cls[0].length);
      continue;
    }
    if(rest[0]==='['){
      const end=rest.indexOf(']');
      const body=rest.slice(1,end);
      rest=rest.slice(end+1);
      const eq=body.indexOf('=');
      if(eq<0){
        if(el.getAttribute(body)==null) return false;
      }else{
        const key=body.slice(0,eq).trim();
        let val=body.slice(eq+1).trim();
        if((val[0]==='"'&&val[val.length-1]==='"')||(val[0]==="'"&&val[val.length-1]==="'")) val=val.slice(1,-1);
        if(el.getAttribute(key)!==val) return false;
      }
      continue;
    }
    return false;
  }
  return true;
}
function _match(el, selector){
  return String(selector||'').split(',').map(s=>s.trim()).filter(Boolean).some(part=>{
    const simple=part.split(/\s+/);
    if(simple.length===1) return _matchOne(el, simple[0]);
    return false;
  });
}
function _findAll(root, selector){
  const parts=String(selector||'').split(',').map(s=>s.trim()).filter(Boolean);
  const out=[];
  const walk=(node)=>{
    for(const child of node.children||[]){
      if(parts.some(part=>_matchOne(child, part))) out.push(child);
      walk(child);
    }
  };
  walk(root);
  return out;
}
function _find(root, selector, _all){
  return _findAll(root, selector)[0]||null;
}

const documentRoot = makeEl('document');
const byId = {};
function register(el){ if(el.id) byId[el.id]=el; return el; }
const document = {
  createElement: (t)=>makeEl(t),
  getElementById(id){ return byId[id]||null; },
  querySelector(sel){ return documentRoot.querySelector(sel); },
  querySelectorAll(sel){ return documentRoot.querySelectorAll(sel); },
};
global.document = document;
global.Node = {
  DOCUMENT_POSITION_FOLLOWING: 4,
  DOCUMENT_POSITION_PRECEDING: 2,
  DOCUMENT_POSITION_CONTAINED_BY: 16,
  DOCUMENT_POSITION_CONTAINS: 8,
};
global.CSS = { escape(s){ return String(s).replace(/"/g,'\\"'); } };
function $(id){ return document.getElementById(id); }
function scrollToBottom(){}
function _assistantTurnBlocks(turn){ return turn?turn.querySelector('.assistant-turn-blocks'):null; }
function _moveLiveRunStatusToTurnEnd(){
  const el=document.getElementById('liveRunStatus');
  const turn=document.getElementById('liveAssistantTurn');
  const blocks=_assistantTurnBlocks(turn);
  if(el&&blocks&&el.parentElement===blocks&&blocks.lastElementChild!==el) blocks.appendChild(el);
}

function mountChat(){
  const inner=makeEl('div');
  inner.id='msgInner';
  register(inner);
  documentRoot.appendChild(inner);
  const turn=makeEl('div');
  turn.id='liveAssistantTurn';
  turn.className='msg-row assistant-turn';
  turn.setAttribute('data-anchor-scene-live-owner','1');
  register(turn);
  const blocks=makeEl('div');
  blocks.className='assistant-turn-blocks';
  turn.appendChild(blocks);
  const worklog=makeEl('div');
  worklog.className='live-worklog worklog';
  worklog.setAttribute('data-live-worklog-shell','1');
  worklog.setAttribute('data-live-activity-current','1');
  worklog.setAttribute('data-tool-worklog-key','live:stream-1');
  worklog.textContent='pre-steer work';
  blocks.appendChild(worklog);
  const footer=makeEl('div');
  footer.id='liveRunStatus';
  register(footer);
  blocks.appendChild(footer);
  inner.appendChild(turn);
  return {inner, turn, blocks, worklog, footer};
}
"""


def _run_node(script: str) -> None:
    result = subprocess.run(
        [NODE, "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"node script failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def test_delivered_steer_parks_after_live_turn_not_inside_it():
    """A delivered Steer must sit after #liveAssistantTurn so in-flight work
    can keep growing above it (parked above the composer)."""
    src = _steer_indicator_src()
    script = textwrap.dedent(
        f"""
        {_DOM_SHIM}
        {src}
        const {{inner, turn, footer}} = mountChat();
        _showSteerIndicator('use python');
        const steer = inner.querySelector('.steer-indicator');
        if(!steer) throw new Error('missing steer indicator');
        if(steer.getAttribute('data-steer-state') !== 'pending') throw new Error('expected pending state, got '+steer.getAttribute('data-steer-state'));
        if(steer.parentElement !== inner) throw new Error('pending steer must be a #msgInner sibling of the live turn');
        if(steer.previousElementSibling !== turn) throw new Error('pending steer must sit immediately after the live turn');
        if(footer.parentElement === steer.parentElement) throw new Error('pending steer must not replace the live footer');
        """
    )
    _run_node(script)


def test_tool_complete_alone_does_not_promote_steer():
    """The consume boundary is the next model iteration after a tool result,
    not the tool_complete itself (steer is applied after the batch)."""
    src = _steer_indicator_src()
    script = textwrap.dedent(
        f"""
        {_DOM_SHIM}
        {src}
        const {{inner, turn}} = mountChat();
        _showSteerIndicator('use python');
        if(typeof _noteSteerToolComplete !== 'function') throw new Error('missing _noteSteerToolComplete');
        _noteSteerToolComplete();
        const steer = inner.querySelector('.steer-indicator');
        if(steer.parentElement !== inner) throw new Error('tool_complete must not move the pending steer');
        if(steer.getAttribute('data-steer-state') !== 'pending') throw new Error('still pending');
        if(steer.previousElementSibling !== turn) throw new Error('must remain after live turn');
        """
    )
    _run_node(script)


def test_model_resume_after_tool_complete_splits_live_turn():
    """After a tool-result boundary, the next model output must pull the Steer
    into the live turn so later worklog/output appears after it."""
    src = _steer_indicator_src()
    script = textwrap.dedent(
        f"""
        {_DOM_SHIM}
        {src}
        const {{inner, turn, blocks, worklog, footer}} = mountChat();
        _showSteerIndicator('use python');
        _noteSteerToolComplete();
        if(typeof _maybePromoteSteerOnModelResume !== 'function') throw new Error('missing _maybePromoteSteerOnModelResume');
        const moved = _maybePromoteSteerOnModelResume();
        if(!moved) throw new Error('model resume after tool_complete must promote');
        const steer = inner.querySelector('.steer-indicator');
        if(steer.getAttribute('data-steer-state') !== 'received') throw new Error('expected received');
        if(steer.parentElement !== blocks) throw new Error('received steer must live inside the live turn');
        if(steer.previousElementSibling !== worklog) throw new Error('received steer must sit after pre-steer worklog');
        if(steer.nextElementSibling !== footer) throw new Error('received steer must sit before the live footer');
        if(turn.getAttribute('data-anchor-scene-live-owner') === '1') throw new Error('scene owner must be cleared so rebuilds cannot flatten the split');
        if(worklog.getAttribute('data-live-activity-current') === '1') throw new Error('pre-steer worklog must be sealed');
        """
    )
    _run_node(script)


def test_model_resume_without_tool_complete_keeps_steer_parked():
    """Tokens that continue the current generation (no tool boundary yet) must
    not claim the model has received the Steer."""
    src = _steer_indicator_src()
    script = textwrap.dedent(
        f"""
        {_DOM_SHIM}
        {src}
        const {{inner, turn}} = mountChat();
        _showSteerIndicator('use python');
        const moved = _maybePromoteSteerOnModelResume();
        if(moved) throw new Error('must not promote before a tool-result boundary');
        const steer = inner.querySelector('.steer-indicator');
        if(steer.parentElement !== inner) throw new Error('must stay parked');
        if(steer.previousElementSibling !== turn) throw new Error('must stay after live turn');
        """
    )
    _run_node(script)


def test_new_pending_steer_does_not_remove_received_steer():
    src = _steer_indicator_src()
    script = textwrap.dedent(
        f"""
        {_DOM_SHIM}
        {src}
        const {{inner, blocks}} = mountChat();
        _showSteerIndicator('first');
        _noteSteerToolComplete();
        _maybePromoteSteerOnModelResume();
        _showSteerIndicator('second');
        const all = inner.querySelectorAll('.steer-indicator');
        if(all.length !== 2) throw new Error('expected received+pending, got '+all.length);
        const received = all.filter?null:null;
        const states = [];
        for(const el of (all.length!==undefined?all:[all])) states.push(el.getAttribute('data-steer-state'));
        // querySelectorAll shim returns a real array
        const list = Array.from(inner.querySelectorAll('.steer-indicator'));
        if(list.length !== 2) throw new Error('expected 2 indicators');
        if(list[0].getAttribute('data-steer-state') !== 'received') throw new Error('first should stay received');
        if(list[1].getAttribute('data-steer-state') !== 'pending') throw new Error('second should be pending');
        if(list[0].parentElement !== blocks) throw new Error('received stays in the turn');
        if(list[1].parentElement !== inner) throw new Error('new pending parks after the live turn');
        """
    )
    _run_node(script)


def test_leftover_removes_pending_keeps_received():
    src = _steer_indicator_src()
    script = textwrap.dedent(
        f"""
        {_DOM_SHIM}
        {src}
        const {{inner, blocks}} = mountChat();
        _showSteerIndicator('kept');
        _noteSteerToolComplete();
        _maybePromoteSteerOnModelResume();
        _showSteerIndicator('leftover');
        if(typeof _removePendingSteerIndicators !== 'function') throw new Error('missing _removePendingSteerIndicators');
        _removePendingSteerIndicators();
        const list = Array.from(inner.querySelectorAll('.steer-indicator'));
        if(list.length !== 1) throw new Error('leftover must drop pending only, got '+list.length);
        if(list[0].getAttribute('data-steer-state') !== 'received') throw new Error('received must survive leftover');
        if(list[0].parentElement !== blocks) throw new Error('received stays in the turn');
        """
    )
    _run_node(script)


def test_ensure_live_worklog_container_creates_group_after_received_steer():
    """Post-receive tool/worklog growth must append after the Steer, not into
    the sealed pre-steer group."""
    helper_src = source_between(
        UI_JS,
        "function _lastReceivedSteerIn(",
        "\nfunction ensureLiveWorklogContainer(",
    )
    # If the helper is not present yet, this source_between will fail — that is
    # the intended base-fail before the fix.
    container_src = source_between(
        UI_JS,
        "function ensureLiveWorklogContainer(",
        "\nfunction _migrateLegacyLiveActivityGroupsToWorklog(",
    )
    script = textwrap.dedent(
        f"""
        {_DOM_SHIM}
        function _activityKeyForLiveTurn(){{ return 'live:stream-1'; }}
        function _syncWorklogReasonFromAnchor(){{}}
        function _migrateLegacyLiveActivityGroupsToWorklog(){{}}
        function _syncToolCallGroupSummary(){{}}
        function _toolWorklogListEl(group){{ return group && group.querySelector('.tool-worklog-list'); }}
        {helper_src}
        {container_src}
        const {{inner, blocks, worklog, footer}} = mountChat();
        const steer=document.createElement('div');
        steer.className='steer-indicator';
        steer.setAttribute('data-steer-state','received');
        blocks.insertBefore(steer, footer);
        worklog.removeAttribute('data-live-activity-current');
        worklog.setAttribute('data-tool-worklog-key','live:stream-1:pre-steer');
        const next=ensureLiveWorklogContainer(blocks, {{activityKey:'live:stream-1'}});
        if(!next) throw new Error('expected a post-steer worklog');
        if(next===worklog) throw new Error('must not reuse the sealed pre-steer worklog');
        if(next.previousElementSibling !== steer) throw new Error('new worklog must sit after the received steer');
        if(footer.previousElementSibling !== next) throw new Error('new worklog must sit before the live footer');
        """
    )
    _run_node(script)


def test_dedupe_keeps_worklogs_on_both_sides_of_received_steer():
    dedupe_src = source_between(
        UI_JS,
        "function _dedupeLiveProcessedWorklogAnchors(",
        "\nfunction isLiveAnchorActivitySceneOwner(",
    )
    helper_src = source_between(
        UI_JS,
        "function _lastReceivedSteerIn(",
        "\nfunction ensureLiveWorklogContainer(",
    )
    score_src = source_between(
        UI_JS,
        "function _liveProcessedWorklogAnchorScore(",
        "\nfunction _dedupeLiveProcessedWorklogAnchors(",
    )
    script = textwrap.dedent(
        f"""
        {_DOM_SHIM}
        function _syncToolCallGroupSummary(){{}}
        {helper_src}
        {score_src}
        {dedupe_src}
        const {{turn, blocks, worklog, footer}} = mountChat();
        const steer=document.createElement('div');
        steer.className='steer-indicator';
        steer.setAttribute('data-steer-state','received');
        blocks.insertBefore(steer, footer);
        const after=document.createElement('div');
        after.className='live-worklog worklog';
        after.setAttribute('data-live-worklog-shell','1');
        after.setAttribute('data-live-activity-current','1');
        after.setAttribute('data-tool-worklog-key','live:stream-1');
        blocks.insertBefore(after, footer);
        _dedupeLiveProcessedWorklogAnchors(turn);
        if(!worklog.parentElement) throw new Error('pre-steer worklog was removed');
        if(!after.parentElement) throw new Error('post-steer worklog was removed');
        """
    )
    _run_node(script)


def test_messages_js_promotes_on_model_resume_after_tool_complete():
    """The live SSE listeners must use the shared consume-boundary helpers."""
    token_idx = MESSAGES_JS.find("source.addEventListener('token'")
    tool_idx = MESSAGES_JS.find("source.addEventListener('tool'")
    complete_idx = MESSAGES_JS.find("source.addEventListener('tool_complete'")
    leftover_idx = MESSAGES_JS.find("source.addEventListener('pending_steer_leftover'")
    assert token_idx > 0 and tool_idx > 0 and complete_idx > 0 and leftover_idx > 0
    token_body = MESSAGES_JS[token_idx:token_idx + 800]
    tool_body = MESSAGES_JS[tool_idx:tool_idx + 900]
    complete_body = MESSAGES_JS[complete_idx:complete_idx + 700]
    leftover_body = MESSAGES_JS[leftover_idx:leftover_idx + 1400]
    assert "_noteSteerToolComplete()" in complete_body, (
        "tool_complete must record the consume boundary for a pending steer"
    )
    assert "_maybePromoteSteerOnModelResume()" in token_body, (
        "token (next model iteration) must promote a pending steer after a tool boundary"
    )
    assert "_maybePromoteSteerOnModelResume()" in tool_body, (
        "a new tool start after a tool boundary is also a next-iteration signal"
    )
    assert "_removePendingSteerIndicators()" in leftover_body, (
        "leftover steer must drop the pending parked indicator"
    )


def test_is_live_anchor_scene_owner_releases_after_received_steer():
    """A received Steer must stop the full-scene rebuild from flattening the split."""
    owner_src = source_between(
        UI_JS,
        "function isLiveAnchorActivitySceneOwner(",
        "\nfunction _projectLiveAnchorActivitySceneForStream(",
    )
    assert "_lastReceivedSteerIn" in owner_src or "data-steer-state" in owner_src, (
        "isLiveAnchorActivitySceneOwner must fail closed once a received steer split the turn"
    )


def test_pending_and_received_styles_are_distinct():
    assert '.steer-indicator[data-steer-state="pending"]' in STYLE_CSS
    assert '.steer-indicator[data-steer-state="received"]' in STYLE_CSS

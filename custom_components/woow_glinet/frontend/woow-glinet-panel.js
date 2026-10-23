function t(t,e,i,s){var o,r=arguments.length,a=r<3?e:null===s?s=Object.getOwnPropertyDescriptor(e,i):s;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)a=Reflect.decorate(t,e,i,s);else for(var n=t.length-1;n>=0;n--)(o=t[n])&&(a=(r<3?o(a):r>3?o(e,i,a):o(e,i))||a);return r>3&&a&&Object.defineProperty(e,i,a),a}"function"==typeof SuppressedError&&SuppressedError;const e=globalThis,i=e.ShadowRoot&&(void 0===e.ShadyCSS||e.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,s=Symbol(),o=new WeakMap;let r=class{constructor(t,e,i){if(this._$cssResult$=!0,i!==s)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o;const e=this.t;if(i&&void 0===t){const i=void 0!==e&&1===e.length;i&&(t=o.get(e)),void 0===t&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),i&&o.set(e,t))}return t}toString(){return this.cssText}};const a=(t,...e)=>{const i=1===t.length?t[0]:e.reduce((e,i,s)=>e+(t=>{if(!0===t._$cssResult$)return t.cssText;if("number"==typeof t)return t;throw Error("Value passed to 'css' function must be a 'css' function result: "+t+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+t[s+1],t[0]);return new r(i,t,s)},n=i?t=>t:t=>t instanceof CSSStyleSheet?(t=>{let e="";for(const i of t.cssRules)e+=i.cssText;return(t=>new r("string"==typeof t?t:t+"",void 0,s))(e)})(t):t,{is:c,defineProperty:l,getOwnPropertyDescriptor:d,getOwnPropertyNames:h,getOwnPropertySymbols:p,getPrototypeOf:u}=Object,f=globalThis,m=f.trustedTypes,_=m?m.emptyScript:"",v=f.reactiveElementPolyfillSupport,b=(t,e)=>t,g={toAttribute(t,e){switch(e){case Boolean:t=t?_:null;break;case Object:case Array:t=null==t?t:JSON.stringify(t)}return t},fromAttribute(t,e){let i=t;switch(e){case Boolean:i=null!==t;break;case Number:i=null===t?null:Number(t);break;case Object:case Array:try{i=JSON.parse(t)}catch(t){i=null}}return i}},y=(t,e)=>!c(t,e),$={attribute:!0,type:String,converter:g,reflect:!1,useDefault:!1,hasChanged:y};Symbol.metadata??=Symbol("metadata"),f.litPropertyMetadata??=new WeakMap;let w=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=$){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){const i=Symbol(),s=this.getPropertyDescriptor(t,i,e);void 0!==s&&l(this.prototype,t,s)}}static getPropertyDescriptor(t,e,i){const{get:s,set:o}=d(this.prototype,t)??{get(){return this[e]},set(t){this[e]=t}};return{get:s,set(e){const r=s?.call(this);o?.call(this,e),this.requestUpdate(t,r,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??$}static _$Ei(){if(this.hasOwnProperty(b("elementProperties")))return;const t=u(this);t.finalize(),void 0!==t.l&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(b("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(b("properties"))){const t=this.properties,e=[...h(t),...p(t)];for(const i of e)this.createProperty(i,t[i])}const t=this[Symbol.metadata];if(null!==t){const e=litPropertyMetadata.get(t);if(void 0!==e)for(const[t,i]of e)this.elementProperties.set(t,i)}this._$Eh=new Map;for(const[t,e]of this.elementProperties){const i=this._$Eu(t,e);void 0!==i&&this._$Eh.set(i,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){const e=[];if(Array.isArray(t)){const i=new Set(t.flat(1/0).reverse());for(const t of i)e.unshift(n(t))}else void 0!==t&&e.push(n(t));return e}static _$Eu(t,e){const i=e.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof t?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),void 0!==this.renderRoot&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){const t=new Map,e=this.constructor.elementProperties;for(const i of e.keys())this.hasOwnProperty(i)&&(t.set(i,this[i]),delete this[i]);t.size>0&&(this._$Ep=t)}createRenderRoot(){const t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((t,s)=>{if(i)t.adoptedStyleSheets=s.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(const i of s){const s=document.createElement("style"),o=e.litNonce;void 0!==o&&s.setAttribute("nonce",o),s.textContent=i.cssText,t.appendChild(s)}})(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,i){this._$AK(t,i)}_$ET(t,e){const i=this.constructor.elementProperties.get(t),s=this.constructor._$Eu(t,i);if(void 0!==s&&!0===i.reflect){const o=(void 0!==i.converter?.toAttribute?i.converter:g).toAttribute(e,i.type);this._$Em=t,null==o?this.removeAttribute(s):this.setAttribute(s,o),this._$Em=null}}_$AK(t,e){const i=this.constructor,s=i._$Eh.get(t);if(void 0!==s&&this._$Em!==s){const t=i.getPropertyOptions(s),o="function"==typeof t.converter?{fromAttribute:t.converter}:void 0!==t.converter?.fromAttribute?t.converter:g;this._$Em=s;const r=o.fromAttribute(e,t.type);this[s]=r??this._$Ej?.get(s)??r,this._$Em=null}}requestUpdate(t,e,i,s=!1,o){if(void 0!==t){const r=this.constructor;if(!1===s&&(o=this[t]),i??=r.getPropertyOptions(t),!((i.hasChanged??y)(o,e)||i.useDefault&&i.reflect&&o===this._$Ej?.get(t)&&!this.hasAttribute(r._$Eu(t,i))))return;this.C(t,e,i)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(t,e,{useDefault:i,reflect:s,wrapped:o},r){i&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,r??e??this[t]),!0!==o||void 0!==r)||(this._$AL.has(t)||(this.hasUpdated||i||(e=void 0),this._$AL.set(t,e)),!0===s&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}const t=this.scheduleUpdate();return null!=t&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[t,e]of this._$Ep)this[t]=e;this._$Ep=void 0}const t=this.constructor.elementProperties;if(t.size>0)for(const[e,i]of t){const{wrapped:t}=i,s=this[e];!0!==t||this._$AL.has(e)||void 0===s||this.C(e,void 0,i,s)}}let t=!1;const e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(t=>t.hostUpdate?.()),this.update(e)):this._$EM()}catch(e){throw t=!1,this._$EM(),e}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(t){}firstUpdated(t){}};w.elementStyles=[],w.shadowRootOptions={mode:"open"},w[b("elementProperties")]=new Map,w[b("finalized")]=new Map,v?.({ReactiveElement:w}),(f.reactiveElementVersions??=[]).push("2.1.2");const x=globalThis,k=t=>t,A=x.trustedTypes,E=A?A.createPolicy("lit-html",{createHTML:t=>t}):void 0,S="$lit$",C=`lit$${Math.random().toFixed(9).slice(2)}$`,M="?"+C,P=`<${M}>`,I=document,T=()=>I.createComment(""),N=t=>null===t||"object"!=typeof t&&"function"!=typeof t,O=Array.isArray,F="[ \t\n\f\r]",B=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,W=/-->/g,U=/>/g,H=RegExp(`>|${F}(?:([^\\s"'>=/]+)(${F}*=${F}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),R=/'/g,z=/"/g,D=/^(?:script|style|textarea|title)$/i,L=t=>(e,...i)=>({_$litType$:t,strings:e,values:i}),j=L(1),q=L(2),V=Symbol.for("lit-noChange"),G=Symbol.for("lit-nothing"),K=new WeakMap,Z=I.createTreeWalker(I,129);function X(t,e){if(!O(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==E?E.createHTML(e):e}const J=(t,e)=>{const i=t.length-1,s=[];let o,r=2===e?"<svg>":3===e?"<math>":"",a=B;for(let e=0;e<i;e++){const i=t[e];let n,c,l=-1,d=0;for(;d<i.length&&(a.lastIndex=d,c=a.exec(i),null!==c);)d=a.lastIndex,a===B?"!--"===c[1]?a=W:void 0!==c[1]?a=U:void 0!==c[2]?(D.test(c[2])&&(o=RegExp("</"+c[2],"g")),a=H):void 0!==c[3]&&(a=H):a===H?">"===c[0]?(a=o??B,l=-1):void 0===c[1]?l=-2:(l=a.lastIndex-c[2].length,n=c[1],a=void 0===c[3]?H:'"'===c[3]?z:R):a===z||a===R?a=H:a===W||a===U?a=B:(a=H,o=void 0);const h=a===H&&t[e+1].startsWith("/>")?" ":"";r+=a===B?i+P:l>=0?(s.push(n),i.slice(0,l)+S+i.slice(l)+C+h):i+C+(-2===l?e:h)}return[X(t,r+(t[i]||"<?>")+(2===e?"</svg>":3===e?"</math>":"")),s]};class Q{constructor({strings:t,_$litType$:e},i){let s;this.parts=[];let o=0,r=0;const a=t.length-1,n=this.parts,[c,l]=J(t,e);if(this.el=Q.createElement(c,i),Z.currentNode=this.el.content,2===e||3===e){const t=this.el.content.firstChild;t.replaceWith(...t.childNodes)}for(;null!==(s=Z.nextNode())&&n.length<a;){if(1===s.nodeType){if(s.hasAttributes())for(const t of s.getAttributeNames())if(t.endsWith(S)){const e=l[r++],i=s.getAttribute(t).split(C),a=/([.?@])?(.*)/.exec(e);n.push({type:1,index:o,name:a[2],strings:i,ctor:"."===a[1]?st:"?"===a[1]?ot:"@"===a[1]?rt:it}),s.removeAttribute(t)}else t.startsWith(C)&&(n.push({type:6,index:o}),s.removeAttribute(t));if(D.test(s.tagName)){const t=s.textContent.split(C),e=t.length-1;if(e>0){s.textContent=A?A.emptyScript:"";for(let i=0;i<e;i++)s.append(t[i],T()),Z.nextNode(),n.push({type:2,index:++o});s.append(t[e],T())}}}else if(8===s.nodeType)if(s.data===M)n.push({type:2,index:o});else{let t=-1;for(;-1!==(t=s.data.indexOf(C,t+1));)n.push({type:7,index:o}),t+=C.length-1}o++}}static createElement(t,e){const i=I.createElement("template");return i.innerHTML=t,i}}function Y(t,e,i=t,s){if(e===V)return e;let o=void 0!==s?i._$Co?.[s]:i._$Cl;const r=N(e)?void 0:e._$litDirective$;return o?.constructor!==r&&(o?._$AO?.(!1),void 0===r?o=void 0:(o=new r(t),o._$AT(t,i,s)),void 0!==s?(i._$Co??=[])[s]=o:i._$Cl=o),void 0!==o&&(e=Y(t,o._$AS(t,e.values),o,s)),e}class tt{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){const{el:{content:e},parts:i}=this._$AD,s=(t?.creationScope??I).importNode(e,!0);Z.currentNode=s;let o=Z.nextNode(),r=0,a=0,n=i[0];for(;void 0!==n;){if(r===n.index){let e;2===n.type?e=new et(o,o.nextSibling,this,t):1===n.type?e=new n.ctor(o,n.name,n.strings,this,t):6===n.type&&(e=new at(o,this,t)),this._$AV.push(e),n=i[++a]}r!==n?.index&&(o=Z.nextNode(),r++)}return Z.currentNode=I,s}p(t){let e=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(t,i,e),e+=i.strings.length-2):i._$AI(t[e])),e++}}class et{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,i,s){this.type=2,this._$AH=G,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=i,this.options=s,this._$Cv=s?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return void 0!==e&&11===t?.nodeType&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=Y(this,t,e),N(t)?t===G||null==t||""===t?(this._$AH!==G&&this._$AR(),this._$AH=G):t!==this._$AH&&t!==V&&this._(t):void 0!==t._$litType$?this.$(t):void 0!==t.nodeType?this.T(t):(t=>O(t)||"function"==typeof t?.[Symbol.iterator])(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==G&&N(this._$AH)?this._$AA.nextSibling.data=t:this.T(I.createTextNode(t)),this._$AH=t}$(t){const{values:e,_$litType$:i}=t,s="number"==typeof i?this._$AC(t):(void 0===i.el&&(i.el=Q.createElement(X(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===s)this._$AH.p(e);else{const t=new tt(s,this),i=t.u(this.options);t.p(e),this.T(i),this._$AH=t}}_$AC(t){let e=K.get(t.strings);return void 0===e&&K.set(t.strings,e=new Q(t)),e}k(t){O(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let i,s=0;for(const o of t)s===e.length?e.push(i=new et(this.O(T()),this.O(T()),this,this.options)):i=e[s],i._$AI(o),s++;s<e.length&&(this._$AR(i&&i._$AB.nextSibling,s),e.length=s)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){const e=k(t).nextSibling;k(t).remove(),t=e}}setConnected(t){void 0===this._$AM&&(this._$Cv=t,this._$AP?.(t))}}class it{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,i,s,o){this.type=1,this._$AH=G,this._$AN=void 0,this.element=t,this.name=e,this._$AM=s,this.options=o,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=G}_$AI(t,e=this,i,s){const o=this.strings;let r=!1;if(void 0===o)t=Y(this,t,e,0),r=!N(t)||t!==this._$AH&&t!==V,r&&(this._$AH=t);else{const s=t;let a,n;for(t=o[0],a=0;a<o.length-1;a++)n=Y(this,s[i+a],e,a),n===V&&(n=this._$AH[a]),r||=!N(n)||n!==this._$AH[a],n===G?t=G:t!==G&&(t+=(n??"")+o[a+1]),this._$AH[a]=n}r&&!s&&this.j(t)}j(t){t===G?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}}class st extends it{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===G?void 0:t}}class ot extends it{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==G)}}class rt extends it{constructor(t,e,i,s,o){super(t,e,i,s,o),this.type=5}_$AI(t,e=this){if((t=Y(this,t,e,0)??G)===V)return;const i=this._$AH,s=t===G&&i!==G||t.capture!==i.capture||t.once!==i.once||t.passive!==i.passive,o=t!==G&&(i===G||s);s&&this.element.removeEventListener(this.name,this,i),o&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}}class at{constructor(t,e,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){Y(this,t)}}const nt=x.litHtmlPolyfillSupport;nt?.(Q,et),(x.litHtmlVersions??=[]).push("3.3.3");const ct=globalThis;class lt extends w{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){const e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=((t,e,i)=>{const s=i?.renderBefore??e;let o=s._$litPart$;if(void 0===o){const t=i?.renderBefore??null;s._$litPart$=o=new et(e.insertBefore(T(),t),t,void 0,i??{})}return o._$AI(t),o})(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return V}}lt._$litElement$=!0,lt.finalized=!0,ct.litElementHydrateSupport?.({LitElement:lt});const dt=ct.litElementPolyfillSupport;dt?.({LitElement:lt}),(ct.litElementVersions??=[]).push("4.2.2");const ht={attribute:!0,type:String,converter:g,reflect:!1,hasChanged:y},pt=(t=ht,e,i)=>{const{kind:s,metadata:o}=i;let r=globalThis.litPropertyMetadata.get(o);if(void 0===r&&globalThis.litPropertyMetadata.set(o,r=new Map),"setter"===s&&((t=Object.create(t)).wrapped=!0),r.set(i.name,t),"accessor"===s){const{name:s}=i;return{set(i){const o=e.get.call(this);e.set.call(this,i),this.requestUpdate(s,o,t,!0,i)},init(e){return void 0!==e&&this.C(s,void 0,t,e),e}}}if("setter"===s){const{name:s}=i;return function(i){const o=this[s];e.call(this,i),this.requestUpdate(s,o,t,!0,i)}}throw Error("Unsupported decorator location: "+s)};function ut(t){return(e,i)=>"object"==typeof i?pt(t,e,i):((t,e,i)=>{const s=e.hasOwnProperty(i);return e.constructor.createProperty(i,t),s?Object.getOwnPropertyDescriptor(e,i):void 0})(t,e,i)}function ft(t){return ut({...t,state:!0,attribute:!1})}class mt{constructor(t){this.hass=t}subscribe(t){return this.hass().connection.subscribeMessage(t,{type:"woow_glinet/subscribe"})}snapshot(){return this.hass().callWS({type:"woow_glinet/snapshot"})}refresh(t){return this.hass().callWS({type:"woow_glinet/refresh",entry_id:t})}setWifi(t,e,i){return this.hass().callWS({type:"woow_glinet/wifi/set",entry_id:t,iface:e,...i})}async wifiKey(t,e){return(await this.hass().callWS({type:"woow_glinet/wifi/key",entry_id:t,iface:e})).key}block(t,e,i){return this.hass().callWS({type:"woow_glinet/client/block",entry_id:t,mac:e,blocked:i})}forget(t,e){return this.hass().callWS({type:"woow_glinet/client/forget",entry_id:t,mac:e})}async clientHistory(t,e){return(await this.hass().callWS({type:"woow_glinet/client/history",entry_id:t,mac:e})).series}addStaticIp(t,e,i,s){return this.hass().callWS({type:"woow_glinet/static_ip/add",entry_id:t,mac:e,ip:i,name:s})}reboot(t){return this.hass().callWS({type:"woow_glinet/reboot",entry_id:t})}}function _t(t,e){customElements.get(t)||customElements.define(t,e)}function vt(t){return t.name||t.alias||t.mac}const bt={title:"WOOW GL.iNet",tab_overview:"Overview",tab_clients:"Devices",tab_wifi:"Wi-Fi",tab_access:"Access",tab_activity:"Activity",loading:"Loading…",no_routers:"No router yet. Add one under Settings › Devices & services › WOOW GL.iNet.",error:"Error: {msg}",cancel:"Cancel",confirm:"Confirm",save:"Save",saving:"Saving…",add:"Add",refresh:"Refresh",copy:"Copy",copied:"Copied",show:"Show",hide:"Hide",just_now:"just now",s_ago:"{n} s ago",m_ago:"{n} min ago",h_ago:"{n} h ago",d_ago:"{n} d ago",updated:"Updated {x}",router_pick:"Router",unreachable:"The router does not answer. Showing what was last read.",mode_router:"Router mode",mode_ap:"Access point mode",mode_wds:"WDS mode",mode_relay:"Repeater mode",mode_mesh:"Mesh mode",mode_passthrough:"Pass-through mode",mode_other:"{mode} mode",mode_note:"In this mode the router is bridged onto another network: it has no NAT or DHCP of its own, so the device list, blocking, fixed IPs and internet traffic are not available here. Wi-Fi and system controls still work.",fact_model:"Model",fact_firmware:"Firmware",fact_address:"Address",fact_lan:"LAN address",fact_uptime:"Uptime",fact_load:"Load (1 / 5 / 15 min)",fact_memory:"Memory",fact_storage:"Storage",fact_internet:"Internet",fact_devices:"Devices",wan_online:"Connected",wan_offline:"No uplink",link_wan:"WAN port",link_wwan:"Wi-Fi uplink",link_tethering:"USB tethering",link_modem:"Cellular",devices_online:"{n} online",devices_split:"{wired} wired · {wireless} Wi-Fi",used_of:"{used} of {total}",traffic_title:"Internet traffic",download:"Download",upload:"Upload",peak:"peak {x}",range_5m:"5 min",range_30m:"30 min",range_all:"All",chart_empty:"Collecting samples…",busiest_title:"Busiest devices",busiest_empty:"Nothing is moving right now.",reboot:"Reboot",reboot_title:"Reboot {router}?",reboot_text:"The network goes down for 1–2 minutes and every device has to reconnect.",rebooting:"Reboot command sent. The router is back in about 1–2 minutes.",search_ph:"Search name, IP or MAC",f_all:"All",f_online:"Online",f_offline:"Offline",f_blocked:"Blocked",sort_speed:"Sort: speed",sort_total:"Sort: total traffic",sort_name:"Sort: name",sort_ip:"Sort: IP address",unnamed:"Unnamed device",iface_cable:"Wired",chip_blocked:"Blocked",chip_static:"Fixed {ip}",chip_limit:"Speed limited",online_for:"online {x}",offline:"offline",total_line:"Total ↓ {rx}  ↑ {tx}",act_block:"Block",act_unblock:"Unblock",act_static:"Fixed IP…",act_forget:"Forget",act_details:"Details",act_copy_mac:"Copy MAC",block_title:"Block {name}?",block_text:"Until you unblock it, this device (by MAC address) can no longer connect to this router.",unblocked_toast:"{name} is unblocked",blocked_toast:"{name} is blocked",forget_title:"Forget {name}?",forget_text:"Removes it from the router's own device list. It shows up again when it reconnects.",forget_all:"Forget offline devices ({n})",forget_all_title:"Forget {n} offline devices?",forget_all_text:"Removes them from the router's own device list, with their names and traffic counters. They show up again when they reconnect.",forgot_n:"Forgot {n} devices",clients_empty:"No device matches.",clients_none:"The router lists no device yet.",history_title:"Speed over the last minutes",history_empty:"Not enough samples yet.",static_title:"Fixed IP for {name}",static_hint:"The router will always give this device this address (a DHCP reservation). This router's API cannot remove it again from here.",ip_address:"IP address",device_name:"Name",static_saved:"Fixed IP {ip} is set",already_static:"Already has a fixed IP ({ip})",band_2g:"2.4 GHz",band_5g:"5 GHz",guest:"Guest",hidden:"Hidden",on_air:"Broadcasting",radio_off:"Off",enabled:"Enabled",ssid:"Network name (SSID)",password:"Password",password_ph:"New password (leave empty to keep)",show_password:"Show current password",wifi_warn:"Devices on this network are disconnected and must reconnect.",wifi_confirm_title:"Change the Wi-Fi “{ssid}”?",wifi_saved:"Saved",wifi_on_toast:"“{ssid}” is on",wifi_off_toast:"“{ssid}” is off",wifi_enc:"Encryption",wifi_channel:"Channel",channel_auto:"auto",wifi_empty:"The router reports no Wi-Fi interface.",blocked_title:"Blocked devices",blocked_empty:"No device is blocked.",unknown_device:"Unknown device",block_by_mac:"Block by MAC address",mac_ph:"AA:BB:CC:DD:EE:FF",pick_client:"Pick a known device…",mode_not_black:"The router is in allow-list mode, where the list means the opposite (only listed devices may connect). Blocking is switched off here to avoid mistakes.",allowed_title:"Allowed devices",static_list_title:"Fixed IP addresses",static_empty:"No fixed IP yet.",static_add_title:"Add a fixed IP",static_remove_why:"Why can't I remove one?",static_remove_text:"On this firmware the router's remove call (lan.remove_static_bind) always answers “Invalid params”, so it cannot be done through the API. To remove one, log in to the router over SSH, find its number with `uci show dhcp`, then run `uci delete dhcp.@host[N]`, `uci commit dhcp` and `/etc/init.d/dnsmasq restart`.",activity_hint:"What changed on the router and who did it: this panel, a service call (scripts, automations, AI agents) or an entity.",activity_empty:"Nothing yet.",all_channels:"All sources",channel_panel:"Panel",channel_service:"Service",channel_entity:"Entity",log_wifi_on:"Wi-Fi “{ssid}” ({iface}) turned on",log_wifi_off:"Wi-Fi “{ssid}” ({iface}) turned off",log_wifi_ssid:"Wi-Fi {iface}: renamed to “{ssid}”",log_wifi_key:"Wi-Fi “{ssid}” ({iface}): password changed",log_wifi_failed:"Wi-Fi {iface}: {error}",log_blocked:"Blocked {name} ({mac})",log_unblocked:"Unblocked {name} ({mac})",log_block_failed:"Could not change the block of {mac}: {error}",log_static_ip_added:"Reserved {ip} for {name} ({mac})",log_static_ip_failed:"Could not reserve {ip} for {mac}: {error}",log_client_forgotten:"Forgot the offline device {name} ({mac})",log_forget_failed:"Could not forget {mac}: {error}",log_rebooted:"Rebooted {router}",log_reboot_failed:"Could not reboot {router}: {error}",err_invalid_mac:"That is not a valid MAC address.",err_invalid_ip:"That is not a valid IPv4 address.",err_bad_ssid:"The network name must be 1–32 bytes (a Chinese character takes 3).",err_bad_key:"The Wi-Fi password must be 8–63 characters.",err_bad_name:"The name cannot be empty.",err_no_such_wifi:"The router has no such Wi-Fi interface.",err_not_router_mode:"Only available in router mode.",err_not_blacklist_mode:"The router is in allow-list mode, so blocking would mean the opposite.",err_ip_outside_lan:"That address cannot be used: it must be inside the router's LAN range and not the network, broadcast or router address.",err_mac_already_bound:"That device already has a fixed IP, and this router's API cannot remove the old one, so it is not added twice.",err_ip_already_bound:"That address is already given to another device.",err_client_online:"Only offline devices can be forgotten.",err_api_error:"The router reported an error",err_not_loaded:"That router is not loaded.",err_failed:"The change failed"},gt={title:"WOOW GL.iNet",tab_overview:"總覽",tab_clients:"裝置",tab_wifi:"WiFi",tab_access:"存取控制",tab_activity:"活動",loading:"載入中…",no_routers:"還沒有路由器。到「設定 › 裝置與服務 › WOOW GL.iNet」新增。",error:"錯誤：{msg}",cancel:"取消",confirm:"確定",save:"儲存",saving:"儲存中…",add:"新增",refresh:"重新整理",copy:"複製",copied:"已複製",show:"顯示",hide:"隱藏",just_now:"剛剛",s_ago:"{n} 秒前",m_ago:"{n} 分鐘前",h_ago:"{n} 小時前",d_ago:"{n} 天前",updated:"{x}更新",router_pick:"路由器",unreachable:"路由器沒有回應，顯示的是最後一次讀到的資料。",mode_router:"路由器模式",mode_ap:"AP 模式",mode_wds:"WDS 模式",mode_relay:"中繼模式",mode_mesh:"Mesh 模式",mode_passthrough:"透傳模式",mode_other:"{mode} 模式",mode_note:"這個模式下路由器是橋接在別的網路上：沒有自己的 NAT 和 DHCP，所以裝置清單、封鎖、固定 IP 和網際網路流量在這裡都不適用。WiFi 和系統控制還是可以用。",fact_model:"型號",fact_firmware:"韌體",fact_address:"連線位址",fact_lan:"LAN 位址",fact_uptime:"已運行",fact_load:"負載（1／5／15 分鐘）",fact_memory:"記憶體",fact_storage:"儲存空間",fact_internet:"網際網路",fact_devices:"裝置",wan_online:"已連線",wan_offline:"沒有上行連線",link_wan:"WAN 孔",link_wwan:"WiFi 上行",link_tethering:"USB 網路共享",link_modem:"行動網路",devices_online:"{n} 台在線",devices_split:"{wired} 有線 · {wireless} 無線",used_of:"{used}／{total}",traffic_title:"網際網路流量",download:"下載",upload:"上傳",peak:"尖峰 {x}",range_5m:"5 分鐘",range_30m:"30 分鐘",range_all:"全部",chart_empty:"收集資料中…",busiest_title:"最忙碌的裝置",busiest_empty:"目前沒有流量。",reboot:"重新開機",reboot_title:"要重新開機「{router}」嗎？",reboot_text:"網路會中斷約 1～2 分鐘，所有裝置都要重新連線。",rebooting:"已送出重新開機指令，約 1～2 分鐘後恢復。",search_ph:"搜尋名稱、IP 或 MAC",f_all:"全部",f_online:"在線",f_offline:"離線",f_blocked:"已封鎖",sort_speed:"排序：目前流量",sort_total:"排序：累計流量",sort_name:"排序：名稱",sort_ip:"排序：IP 位址",unnamed:"未命名裝置",iface_cable:"有線",chip_blocked:"已封鎖",chip_static:"固定 {ip}",chip_limit:"已限速",online_for:"在線 {x}",offline:"離線",total_line:"累計 ↓ {rx}  ↑ {tx}",act_block:"封鎖",act_unblock:"解除封鎖",act_static:"固定 IP…",act_forget:"移除記錄",act_details:"詳細",act_copy_mac:"複製 MAC",block_title:"要封鎖「{name}」嗎？",block_text:"解除封鎖之前，這台裝置（依 MAC 位址）沒辦法再連上這台路由器。",unblocked_toast:"已解除封鎖 {name}",blocked_toast:"已封鎖 {name}",forget_title:"要移除「{name}」的記錄嗎？",forget_text:"會從路由器自己的裝置清單拿掉，它下次連線時又會出現。",forget_all:"清除離線裝置（{n}）",forget_all_title:"要清除 {n} 台離線裝置嗎？",forget_all_text:"會從路由器自己的裝置清單拿掉（連同名稱和流量計數），它們下次連線時又會出現。",forgot_n:"已清除 {n} 台",clients_empty:"沒有符合的裝置。",clients_none:"路由器上還沒有任何裝置記錄。",history_title:"最近的流量",history_empty:"資料還不夠。",static_title:"為「{name}」設定固定 IP",static_hint:"路由器之後都會把這個位址給這台裝置（DHCP 固定租約）。注意：這台路由器的 API 沒辦法從這裡再移除它。",ip_address:"IP 位址",device_name:"名稱",static_saved:"已設定固定 IP {ip}",already_static:"已經有固定 IP（{ip}）",band_2g:"2.4 GHz",band_5g:"5 GHz",guest:"訪客",hidden:"隱藏",on_air:"廣播中",radio_off:"關閉",enabled:"啟用",ssid:"網路名稱（SSID）",password:"密碼",password_ph:"新密碼（不改就留空）",show_password:"顯示目前密碼",wifi_warn:"這個網路上的裝置會被中斷，要重新連線。",wifi_confirm_title:"要修改 WiFi「{ssid}」嗎？",wifi_saved:"已儲存",wifi_on_toast:"「{ssid}」已開啟",wifi_off_toast:"「{ssid}」已關閉",wifi_enc:"加密",wifi_channel:"頻道",channel_auto:"自動",wifi_empty:"路由器沒有回報任何 WiFi 介面。",blocked_title:"已封鎖的裝置",blocked_empty:"沒有封鎖任何裝置。",unknown_device:"不明裝置",block_by_mac:"用 MAC 位址封鎖",mac_ph:"AA:BB:CC:DD:EE:FF",pick_client:"選一台已知的裝置…",mode_not_black:"路由器目前是白名單模式（只有清單內的裝置能連線），封鎖的意義剛好相反，這裡先停用以免誤操作。",allowed_title:"允許的裝置",static_list_title:"固定 IP",static_empty:"還沒有固定 IP。",static_add_title:"新增固定 IP",static_remove_why:"為什麼不能移除？",static_remove_text:"這個韌體上，路由器的移除指令（lan.remove_static_bind）不管怎麼傳都回「Invalid params」，所以沒辦法透過 API 做。要移除請用 SSH 登入路由器，先用 `uci show dhcp` 找出它的編號，再執行 `uci delete dhcp.@host[N]`、`uci commit dhcp` 和 `/etc/init.d/dnsmasq restart`。",activity_hint:"路由器上改了什麼、是誰改的：這個面板、服務呼叫（腳本、自動化、AI 代理）或實體。",activity_empty:"目前沒有紀錄。",all_channels:"全部來源",channel_panel:"面板",channel_service:"服務",channel_entity:"實體",log_wifi_on:"WiFi「{ssid}」（{iface}）已開啟",log_wifi_off:"WiFi「{ssid}」（{iface}）已關閉",log_wifi_ssid:"WiFi {iface}：名稱改為「{ssid}」",log_wifi_key:"WiFi「{ssid}」（{iface}）：密碼已更改",log_wifi_failed:"WiFi {iface}：{error}",log_blocked:"已封鎖 {name}（{mac}）",log_unblocked:"已解除封鎖 {name}（{mac}）",log_block_failed:"沒能改變 {mac} 的封鎖：{error}",log_static_ip_added:"已為 {name}（{mac}）固定 {ip}",log_static_ip_failed:"沒能為 {mac} 固定 {ip}：{error}",log_client_forgotten:"已移除離線裝置 {name}（{mac}）的記錄",log_forget_failed:"沒能移除 {mac} 的記錄：{error}",log_rebooted:"已重新開機 {router}",log_reboot_failed:"沒能重新開機 {router}：{error}",err_invalid_mac:"這不是有效的 MAC 位址。",err_invalid_ip:"這不是有效的 IPv4 位址。",err_bad_ssid:"網路名稱要 1～32 個位元組（一個中文字佔 3 個）。",err_bad_key:"WiFi 密碼要 8～63 個字元。",err_bad_name:"名稱不能是空的。",err_no_such_wifi:"路由器沒有這個 WiFi 介面。",err_not_router_mode:"只有路由器模式才能用。",err_not_blacklist_mode:"路由器目前是白名單模式，封鎖的意義會剛好相反。",err_ip_outside_lan:"這個位址不能用：要在路由器的 LAN 網段內，而且不是網段位址、廣播位址或路由器自己。",err_mac_already_bound:"這台裝置已經有固定 IP，而這台路由器的 API 沒辦法移除舊的，所以不重複新增。",err_ip_already_bound:"這個位址已經給了另一台裝置。",err_client_online:"只能移除離線裝置的記錄。",err_api_error:"路由器回報錯誤",err_not_loaded:"這台路由器沒有載入。",err_failed:"沒能完成修改"};function yt(t){const e=t.toLowerCase().startsWith("zh")?gt:bt;return(t,i)=>{let s=e[t]??bt[t]??t;if(i)for(const[t,e]of Object.entries(i))s=s.split(`{${t}}`).join(String(e));return s}}function $t(t){return t in bt}function wt(t,e){const i=t&&"object"==typeof t&&"code"in t?String(t.code):"",s=String(t&&"object"==typeof t&&"message"in t?t.message:t),o=`err_${i}`;return $t(o)?"api_error"===i||"failed"===i?`${e(o)}: ${s}`:e(o):e("error",{msg:s})}function xt(t,e){const i=Math.max(0,Date.now()/1e3-t);return i<5?e("just_now"):i<60?e("s_ago",{n:Math.floor(i)}):i<3600?e("m_ago",{n:Math.floor(i/60)}):i<86400?e("h_ago",{n:Math.floor(i/3600)}):e("d_ago",{n:Math.floor(i/86400)})}function kt(t,e=!0){const i=new Date(1e3*t),s=t=>String(t).padStart(2,"0");return e?`${s(i.getHours())}:${s(i.getMinutes())}:${s(i.getSeconds())}`:`${s(i.getHours())}:${s(i.getMinutes())}`}const At=["B","kB","MB","GB","TB"];function Et(t){let e=Math.max(0,t),i=0;for(;e>=1e3&&i<At.length-1;)e/=1e3,i+=1;const s=0===i||e>=100?0:e>=10?1:2;return`${e.toFixed(s)} ${At[i]}`}function St(t){return`${Et(t)}/s`}const Ct=a`
  :host {
    display: block;
    color: var(--primary-text-color);
    font-family: var(--paper-font-body1_-_font-family, Roboto, "Noto Sans TC", sans-serif);
  }
  .card {
    background: var(--card-background-color, #fff);
    border: 1px solid var(--divider-color, #e0e0e0);
    border-radius: var(--ha-card-border-radius, 12px);
    padding: 16px;
    margin-bottom: 16px;
  }
  .card h2 {
    margin: 0 0 12px;
    font-size: 1.1em;
    font-weight: 500;
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }
  .grow {
    flex: 1 1 auto;
    min-width: 0;
  }
  .muted {
    color: var(--secondary-text-color);
    font-size: 0.9em;
  }
  .mono {
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 0.92em;
    word-break: break-all;
  }
  .chip {
    display: inline-block;
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 0.8em;
    line-height: 1.6;
    background: var(--secondary-background-color, #eee);
    color: var(--secondary-text-color);
    white-space: nowrap;
  }
  .chip.ok {
    background: rgba(67, 160, 71, 0.15);
    color: var(--success-color, #43a047);
  }
  .chip.warn {
    background: rgba(255, 152, 0, 0.15);
    color: var(--warning-color, #ff9800);
  }
  .chip.bad {
    background: rgba(219, 68, 55, 0.12);
    color: var(--error-color, #db4437);
  }
  .chip.info {
    background: rgba(3, 169, 244, 0.14);
    color: var(--info-color, #039be5);
  }
  button {
    font: inherit;
    border: 1px solid var(--divider-color, #ccc);
    background: var(--card-background-color, #fff);
    color: var(--primary-text-color);
    border-radius: 8px;
    padding: 4px 10px;
    cursor: pointer;
  }
  button:hover {
    border-color: var(--primary-color);
  }
  button.primary {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: var(--text-primary-color, #fff);
  }
  button.link {
    border: none;
    background: none;
    color: var(--primary-color);
    padding: 2px 4px;
  }
  button.danger {
    color: var(--error-color, #db4437);
  }
  button.primary.danger {
    background: var(--error-color, #db4437);
    border-color: var(--error-color, #db4437);
    color: #fff;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  input,
  select {
    font: inherit;
    color: var(--primary-text-color);
    background: var(--card-background-color, #fff);
    border: 1px solid var(--divider-color, #ccc);
    border-radius: 8px;
    padding: 6px 8px;
    min-width: 0;
  }
  input:focus,
  select:focus {
    outline: 2px solid var(--primary-color);
    outline-offset: -1px;
  }
  .empty {
    padding: 24px 8px;
    text-align: center;
    color: var(--secondary-text-color);
  }
  .rx {
    color: var(--success-color, #43a047);
  }
  .tx {
    color: var(--info-color, #039be5);
  }
  .dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--disabled-text-color, #9e9e9e);
    flex: none;
  }
  .dot.on {
    background: var(--success-color, #43a047);
  }
  .dot.bad {
    background: var(--error-color, #db4437);
  }
  .banner {
    padding: 10px 12px;
    border-radius: 8px;
    background: rgba(255, 152, 0, 0.12);
    color: var(--primary-text-color);
    font-size: 0.92em;
    margin-bottom: 12px;
  }
  .banner.bad {
    background: rgba(219, 68, 55, 0.12);
  }
  .error {
    padding: 8px 10px;
    border-radius: 8px;
    background: rgba(219, 68, 55, 0.12);
    color: var(--error-color, #db4437);
    font-size: 0.9em;
  }
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 10;
    background: rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
  }
  .dialog {
    width: min(460px, 100%);
    max-height: 92vh;
    overflow: auto;
    background: var(--card-background-color, #fff);
    border-radius: 12px;
    padding: 20px;
    display: grid;
    gap: 12px;
  }
  .dialog h2 {
    margin: 0;
    font-size: 1.15em;
    font-weight: 500;
  }
  .dialog label {
    display: grid;
    gap: 4px;
    font-size: 0.85em;
    color: var(--secondary-text-color);
  }
  .dialog input,
  .dialog select {
    font-size: 1.05em;
  }
`;function Mt(t,e){t.dispatchEvent(new CustomEvent("confirm",{detail:e,bubbles:!0,composed:!0}))}function Pt(t,e,i=!0){t.dispatchEvent(new CustomEvent("notify",{detail:{text:e,ok:i},bubbles:!0,composed:!0}))}const It=t=>t.target.value;class Tt extends lt{constructor(){super(...arguments),this.blockMac="",this.blockError="",this.busy=!1,this.fixMac="",this.fixIp="",this.fixName="",this.fixError=""}nameOf(t){const e=t.toUpperCase(),i=this.router.clients.find(t=>t.mac.toUpperCase()===e);if(i)return vt(i);const s=this.router.static_binds.find(t=>(t.mac??"").toUpperCase()===e);return s?.name||this.t("unknown_device")}async setBlocked(t,e){const i=this.t;this.busy=!0,this.blockError="";try{await this.api.block(this.router.entry_id,t,e),Pt(this,i(e?"blocked_toast":"unblocked_toast",{name:this.nameOf(t)})),e&&(this.blockMac="")}catch(t){this.blockError=wt(t,i)}finally{this.busy=!1}}block(t){const e=this.t;Mt(this,{title:e("block_title",{name:this.nameOf(t)}),text:e("block_text"),action:e("act_block"),danger:!0,run:()=>this.setBlocked(t,!0)})}pickBlock(t){this.blockMac=t}pickFix(t){const e=this.router.clients.find(e=>e.mac===t);this.fixMac=t,e&&(this.fixIp=e.ip,this.fixName=vt(e)===e.mac?"":vt(e))}async addFix(){this.busy=!0,this.fixError="";try{await this.api.addStaticIp(this.router.entry_id,this.fixMac.trim(),this.fixIp.trim(),this.fixName.trim()),Pt(this,this.t("static_saved",{ip:this.fixIp.trim()})),this.fixMac=this.fixIp=this.fixName=""}catch(t){this.fixError=wt(t,this.t)}finally{this.busy=!1}}renderBlocklist(){const t=this.t,e=this.router.blocklist;if("black"!==e.mode)return j`<div class="card">
        <h2>${t("allowed_title")}</h2>
        <div class="banner">${t("mode_not_black")}</div>
        ${0===e.white.length?j`<div class="muted">${t("blocked_empty")}</div>`:e.white.map(t=>j`<div class="item"><div class="who"><b>${this.nameOf(t)}</b><div class="mono muted">${t}</div></div></div>`)}
      </div>`;const i=this.router.clients.filter(t=>!t.blocked);return j`<div class="card">
      <h2>${t("blocked_title")}</h2>
      ${0===e.black.length?j`<div class="muted">${t("blocked_empty")}</div>`:e.black.map(e=>j`<div class="item">
              <span class="dot bad"></span>
              <div class="who"><b>${this.nameOf(e)}</b><div class="mono muted">${e}</div></div>
              <button ?disabled=${this.busy} @click=${()=>this.setBlocked(e,!1)}>${t("act_unblock")}</button>
            </div>`)}
      <div class="muted" style="margin-top:14px">${t("block_by_mac")}</div>
      <div class="add">
        <select @change=${t=>this.pickBlock(It(t))} aria-label=${t("pick_client")}>
          <option value="">${t("pick_client")}</option>
          ${i.map(t=>j`<option value=${t.mac} ?selected=${t.mac===this.blockMac}>${vt(t)} · ${t.ip}</option>`)}
        </select>
        <input class="mono" placeholder=${t("mac_ph")} .value=${this.blockMac} @input=${t=>this.blockMac=It(t)}
          @keydown=${t=>"Enter"===t.key&&this.blockMac.trim()&&this.block(this.blockMac.trim())} />
        <button class="danger" ?disabled=${this.busy||!this.blockMac.trim()} @click=${()=>this.block(this.blockMac.trim())}>${t("act_block")}</button>
      </div>
      ${this.blockError?j`<div class="error" style="margin-top:8px">${this.blockError}</div>`:G}
    </div>`}renderStatic(){const t=this.t,e=this.router.static_binds,i=new Set(e.map(t=>(t.mac??"").toUpperCase())),s=this.router.clients.filter(t=>!i.has(t.mac.toUpperCase()));return j`<div class="card">
      <h2>${t("static_list_title")}</h2>
      ${0===e.length?j`<div class="muted">${t("static_empty")}</div>`:e.map(t=>j`<div class="item">
              <span class="dot on"></span>
              <div class="who"><b>${t.name||this.nameOf(t.mac)}</b><div class="muted"><span class="mono">${t.ip}</span> · <span class="mono">${t.mac}</span></div></div>
            </div>`)}
      <details>
        <summary>${t("static_remove_why")}</summary>
        <p>${t("static_remove_text")}</p>
      </details>
      <div class="muted" style="margin-top:14px">${t("static_add_title")}</div>
      <div class="add">
        <select @change=${t=>this.pickFix(It(t))} aria-label=${t("pick_client")}>
          <option value="">${t("pick_client")}</option>
          ${s.map(t=>j`<option value=${t.mac} ?selected=${t.mac===this.fixMac}>${vt(t)} · ${t.ip}</option>`)}
        </select>
        <input class="mono" placeholder=${t("mac_ph")} .value=${this.fixMac} @input=${t=>this.fixMac=It(t)} />
        <input class="mono" placeholder=${t("ip_address")} .value=${this.fixIp} @input=${t=>this.fixIp=It(t)} />
        <input placeholder=${t("device_name")} .value=${this.fixName} @input=${t=>this.fixName=It(t)}
          @keydown=${t=>"Enter"===t.key&&this.addFix()} />
        <button class="primary" ?disabled=${this.busy||!this.fixMac.trim()||!this.fixIp.trim()||!this.fixName.trim()} @click=${()=>this.addFix()}>${t("add")}</button>
      </div>
      ${this.fixError?j`<div class="error" style="margin-top:8px">${this.fixError}</div>`:G}
    </div>`}render(){return j`${this.renderBlocklist()}${this.renderStatic()}`}}Tt.styles=[Ct,a`
      .item {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px 12px;
        padding: 8px 0;
        border-top: 1px solid var(--divider-color, #eee);
      }
      .item:first-of-type {
        border-top: none;
      }
      .who {
        flex: 1 1 200px;
        min-width: 0;
      }
      .add {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 12px;
      }
      .add input {
        flex: 1 1 160px;
      }
      details {
        margin-top: 10px;
        font-size: 0.9em;
        color: var(--secondary-text-color);
      }
      summary {
        cursor: pointer;
      }
      details p {
        margin: 6px 0 0;
        line-height: 1.5;
      }
    `],t([ut({attribute:!1})],Tt.prototype,"router",void 0),t([ut({attribute:!1})],Tt.prototype,"t",void 0),t([ut({attribute:!1})],Tt.prototype,"api",void 0),t([ft()],Tt.prototype,"blockMac",void 0),t([ft()],Tt.prototype,"blockError",void 0),t([ft()],Tt.prototype,"busy",void 0),t([ft()],Tt.prototype,"fixMac",void 0),t([ft()],Tt.prototype,"fixIp",void 0),t([ft()],Tt.prototype,"fixName",void 0),t([ft()],Tt.prototype,"fixError",void 0),_t("woow-glinet-access",Tt);class Nt extends lt{constructor(){super(...arguments),this.entries=[],this.now=0,this.multi=!1,this.channel=""}channelLabel(t){const e=`channel_${t}`;return $t(e)?this.t(e):t}message(t){const e=`log_${t.msg}`;if(!t.msg||!$t(e))return t.summary;const i={...t.args},s=`err_${i.code}`;return"error"in i&&$t(s)&&(i.error=this.t(s)),this.t(e,i)}render(){const t=this.t,e=this.entries.filter(t=>!this.channel||t.channel===this.channel).sort((t,e)=>e.t-t.t);return j`<div class="card">
      <div class="row">
        <h2 class="grow">${t("tab_activity")}</h2>
        <select @change=${t=>this.channel=(t=>t.target.value)(t)}>
          <option value="">${t("all_channels")}</option>
          ${["panel","service","entity"].map(t=>j`<option value=${t}>${this.channelLabel(t)}</option>`)}
        </select>
      </div>
      <div class="muted">${t("activity_hint")}</div>
      ${0===e.length?j`<div class="empty">${t("activity_empty")}</div>`:e.map(e=>j`<div class="entry">
              <div class="when" title=${new Date(1e3*e.t).toLocaleString()}>${xt(e.t,t)}<br />${kt(e.t)}</div>
              <div>
                <div class="row">
                  <span class="chip ${"service"===e.channel?"info":""}">${this.channelLabel(e.channel)}</span>
                  ${e.user?j`<span class="chip">${e.user}</span>`:G}
                  ${this.multi&&e.router?j`<span class="chip ok">${e.router}</span>`:G}
                </div>
                <div class=${e.ok?"":"fail"} title=${e.summary}>${e.ok?"":"✗ "}${this.message(e)}</div>
              </div>
            </div>`)}
    </div>`}}Nt.styles=[Ct,a`
      .entry {
        display: grid;
        grid-template-columns: 7.5em 1fr;
        gap: 4px 12px;
        padding: 10px 0;
        border-top: 1px solid var(--divider-color, #eee);
      }
      .when {
        color: var(--secondary-text-color);
        font-size: 0.85em;
      }
      .fail {
        color: var(--error-color, #db4437);
      }
    `],t([ut({attribute:!1})],Nt.prototype,"entries",void 0),t([ut({attribute:!1})],Nt.prototype,"now",void 0),t([ut({attribute:!1})],Nt.prototype,"t",void 0),t([ut({type:Boolean})],Nt.prototype,"multi",void 0),t([ft()],Nt.prototype,"channel",void 0),_t("woow-glinet-activity",Nt);const Ot={l:4,r:4,t:16,b:18};class Ft extends lt{constructor(){super(...arguments),this.samples=[],this.window=0,this.compact=!1,this.height=0,this.width=600,this.hover=null}connectedCallback(){super.connectedCallback(),this.observer=new ResizeObserver(t=>{const e=Math.round(t[0].contentRect.width);e>0&&e!==this.width&&(this.width=e)}),this.observer.observe(this)}disconnectedCallback(){super.disconnectedCallback(),this.observer?.disconnect()}get visible(){const t=this.samples;if(!this.window||0===t.length)return t;const e=t[t.length-1][0]-this.window,i=t.findIndex(t=>t[0]>=e);return i<0?[]:t.slice(i)}onMove(t,e,i){const s=t.currentTarget.getBoundingClientRect(),o=t.clientX-s.left;let r=0;for(let t=1;t<e.length;t++)Math.abs(i(e[t][0])-o)<Math.abs(i(e[r][0])-o)&&(r=t);this.hover=r}render(){const t=this.visible,e=this.height||(this.compact?44:170);if(t.length<2)return j`<div class="none" style="height:${e}px">${this.compact?G:this.t("chart_empty")}</div>`;const i=this.compact?{l:2,r:2,t:3,b:3}:Ot,s=this.width,o=t[0][0],r=t[t.length-1][0],a=function(t){if(t<=0)return 1;const e=Math.pow(10,Math.floor(Math.log10(t)));for(const i of[1,2,5,10])if(i*e>=t)return i*e;return 10*e}(Math.max(1e3,...t.map(t=>Math.max(t[1],t[2])))),n=t=>i.l+(t-o)/(r-o||1)*(s-i.l-i.r),c=t=>e-i.b-t/a*(e-i.t-i.b),l=c(0),d=e=>t.map((t,i)=>`${i?"L":"M"}${n(t[0]).toFixed(1)},${c(t[e]).toFixed(1)}`).join(" "),h=t=>`${d(t)} L${n(r).toFixed(1)},${l} L${n(o).toFixed(1)},${l} Z`,p=null!==this.hover?t[Math.min(this.hover,t.length-1)]:null,u=r-o<600;return j`<svg
        viewBox="0 0 ${s} ${e}"
        height=${e}
        @pointermove=${e=>!this.compact&&this.onMove(e,t,n)}
        @pointerleave=${()=>this.hover=null}
      >
        ${this.compact?G:q`
            <line class="grid" x1=${i.l} x2=${s-i.r} y1=${c(a)} y2=${c(a)}></line>
            <line class="grid" x1=${i.l} x2=${s-i.r} y1=${c(a/2)} y2=${c(a/2)}></line>
            <line class="grid" x1=${i.l} x2=${s-i.r} y1=${l} y2=${l}></line>
            <text class="axis" x=${i.l+2} y=${c(a)-2}>${St(a)}</text>
            <text class="axis" x=${i.l+2} y=${c(a/2)-2}>${St(a/2)}</text>
            <text class="axis" x=${i.l} y=${e-4}>${kt(o,u)}</text>
            <text class="axis" x=${s-i.r} y=${e-4} text-anchor="end">${kt(r,u)}</text>`}
        ${q`
          <path class="area rx" d=${h(1)}></path>
          <path class="area tx" d=${h(2)}></path>
          <path class="line rx" d=${d(1)}></path>
          <path class="line tx" d=${d(2)}></path>`}
        ${p?q`<line class="cursor" x1=${n(p[0])} x2=${n(p[0])} y1=${i.t} y2=${l}></line>`:G}
      </svg>
      ${p?j`<div class="tip" style="left:${Math.min(Math.max(n(p[0])-70,0),s-150)}px">
            <b>${kt(p[0])}</b>
            <span class="rx">↓ ${St(p[1])}</span> <span class="tx">↑ ${St(p[2])}</span>
          </div>`:G}`}}Ft.styles=[Ct,a`
      :host {
        position: relative;
        display: block;
      }
      svg {
        display: block;
        width: 100%;
        touch-action: pan-y;
      }
      .grid {
        stroke: var(--divider-color, #e0e0e0);
        stroke-width: 1;
      }
      .axis {
        fill: var(--secondary-text-color);
        font-size: 10px;
      }
      .line {
        fill: none;
        stroke-width: 1.5;
        stroke-linejoin: round;
      }
      .line.rx {
        stroke: var(--success-color, #43a047);
      }
      .line.tx {
        stroke: var(--info-color, #039be5);
      }
      .area.rx {
        fill: var(--success-color, #43a047);
        fill-opacity: 0.16;
      }
      .area.tx {
        fill: var(--info-color, #039be5);
        fill-opacity: 0.16;
      }
      .cursor {
        stroke: var(--secondary-text-color);
        stroke-width: 1;
        stroke-dasharray: 3 3;
      }
      .tip {
        position: absolute;
        top: 0;
        pointer-events: none;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.8em;
        white-space: nowrap;
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #ccc);
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
      }
      .none {
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--secondary-text-color);
        font-size: 0.9em;
      }
    `],t([ut({attribute:!1})],Ft.prototype,"samples",void 0),t([ut({attribute:!1})],Ft.prototype,"t",void 0),t([ut({type:Number})],Ft.prototype,"window",void 0),t([ut({type:Boolean})],Ft.prototype,"compact",void 0),t([ut({type:Number})],Ft.prototype,"height",void 0),t([ft()],Ft.prototype,"width",void 0),t([ft()],Ft.prototype,"hover",void 0),_t("woow-glinet-chart",Ft);const Bt=["all","online","offline","blocked"],Wt=["speed","total","name","ip"],Ut=t=>t.target.value,Ht=t=>t.split(".").reduce((t,e)=>256*t+(Number(e)||0),0);class Rt extends lt{constructor(){super(...arguments),this.now=0,this.query="",this.filter="all",this.sort="speed",this.open=null,this.history=[],this.busy=null,this.fixing=null,this.fixIp="",this.fixName="",this.fixError="",this.fixBusy=!1}willUpdate(t){if(t.has("router")&&this.open){const t=this.router.clients.find(t=>t.mac===this.open),e=this.history[this.history.length-1],i=Date.now()/1e3;t&&t.online&&(!e||i-e[0]>=2)&&(this.history=[...this.history,[i,t.rx,t.tx]].slice(-360))}}async toggleDetails(t){if(this.open!==t.mac){this.open=t.mac,this.history=[];try{const e=await this.api.clientHistory(this.router.entry_id,t.mac);this.open===t.mac&&(this.history=e)}catch{}}else this.open=null}visible(){const t=this.query.trim().toLowerCase(),e=this.router.clients.filter(e=>!("online"===this.filter&&!e.online)&&(("offline"!==this.filter||!e.online)&&(!("blocked"===this.filter&&!e.blocked)&&(!t||[e.name,e.alias,e.ip,e.mac].some(e=>e.toLowerCase().includes(t)))))),i={speed:(t,e)=>e.rx+e.tx-(t.rx+t.tx)||Number(e.online)-Number(t.online)||vt(t).localeCompare(vt(e)),total:(t,e)=>e.total_rx+e.total_tx-(t.total_rx+t.total_tx),name:(t,e)=>vt(t).localeCompare(vt(e)),ip:(t,e)=>Ht(t.ip)-Ht(e.ip)};return e.sort(i[this.sort])}count(t){const e=this.router.clients;return"online"===t?e.filter(t=>t.online).length:"offline"===t?e.filter(t=>!t.online).length:"blocked"===t?e.filter(t=>t.blocked).length:e.length}async setBlocked(t,e){const i=this.t;this.busy=t.mac;try{await this.api.block(this.router.entry_id,t.mac,e),Pt(this,i(e?"blocked_toast":"unblocked_toast",{name:vt(t)}))}catch(t){Pt(this,wt(t,i),!1)}finally{this.busy=null}}block(t){const e=this.t;Mt(this,{title:e("block_title",{name:vt(t)}),text:e("block_text"),action:e("act_block"),danger:!0,run:()=>this.setBlocked(t,!0)})}forget(t){const e=this.t;Mt(this,{title:e("forget_title",{name:vt(t)}),text:e("forget_text"),action:e("act_forget"),danger:!0,run:async()=>{try{await this.api.forget(this.router.entry_id,t.mac)}catch(t){Pt(this,wt(t,e),!1)}}})}forgetAll(){const t=this.t,e=this.router.clients.filter(t=>!t.online);Mt(this,{title:t("forget_all_title",{n:e.length}),text:t("forget_all_text"),action:t("act_forget"),danger:!0,run:async()=>{let i=0;for(const s of e)try{await this.api.forget(this.router.entry_id,s.mac),i+=1}catch(e){Pt(this,wt(e,t),!1);break}i&&Pt(this,t("forgot_n",{n:i}))}})}startFix(t){this.fixing=t,this.fixIp=t.ip,this.fixName=vt(t)===t.mac?"":vt(t),this.fixError=""}async confirmFix(){const t=this.fixing;if(t&&!this.fixBusy){this.fixBusy=!0,this.fixError="";try{await this.api.addStaticIp(this.router.entry_id,t.mac,this.fixIp.trim(),this.fixName.trim()),Pt(this,this.t("static_saved",{ip:this.fixIp.trim()})),this.fixing=null}catch(t){this.fixError=wt(t,this.t)}finally{this.fixBusy=!1}}}renderClient(t){const e=this.t,i=this.busy===t.mac,s=this.open===t.mac;return j`<div class="client ${t.online?"":"off"}">
      <div class="row" style="flex-wrap:nowrap">
        <span class="dot ${t.blocked?"bad":t.online?"on":""}" title=${t.online?"":e("offline")}></span>
        <span class="name grow" title=${vt(t)}>${t.name||t.alias||e("unnamed")}</span>
        ${t.iface?j`<span class="chip">${function(t,e){return"cable"===t?e("iface_cable"):t}(t.iface,e)}</span>`:G}
      </div>
      <div class="row">
        ${t.blocked?j`<span class="chip bad">${e("chip_blocked")}</span>`:G}
        ${t.static_ip?j`<span class="chip info">${e("chip_static",{ip:t.static_ip})}</span>`:G}
        ${t.limit_rx||t.limit_tx?j`<span class="chip warn">${e("chip_limit")}</span>`:G}
      </div>
      <div class="muted"><span class="mono">${t.ip||"—"}</span> · <span class="mono">${t.mac}</span></div>
      <div class="row stats">
        ${t.online?j`<span class="rx">↓ ${St(t.rx)}</span><span class="tx">↑ ${St(t.tx)}</span>
              ${t.since?j`<span class="muted">${e("online_for",{x:xt(t.since,e).replace(/\s*(ago|前)$/,"")})}</span>`:G}`:j`<span class="muted">${e("offline")}</span>`}
      </div>
      <div class="muted">${e("total_line",{rx:Et(t.total_rx),tx:Et(t.total_tx)})}</div>
      <div class="row actions">
        ${t.blocked?j`<button ?disabled=${i} @click=${()=>this.setBlocked(t,!1)}>${e("act_unblock")}</button>`:j`<button class="danger" ?disabled=${i} @click=${()=>this.block(t)}>${e("act_block")}</button>`}
        <button ?disabled=${!!t.static_ip} title=${t.static_ip?e("already_static",{ip:t.static_ip}):""} @click=${()=>this.startFix(t)}>${e("act_static")}</button>
        ${t.online?G:j`<button class="danger" @click=${()=>this.forget(t)}>${e("act_forget")}</button>`}
        <span class="grow"></span>
        <button class="link" @click=${()=>this.toggleDetails(t)}>${e("act_details")} ${s?"▴":"▾"}</button>
      </div>
      ${s?j`<div class="detail">
            <div class="row"><span class="muted">${e("history_title")}</span><span class="grow"></span>
              <button class="link" @click=${()=>{!function(t){if(navigator.clipboard&&window.isSecureContext)return void navigator.clipboard.writeText(t);const e=document.createElement("textarea");e.value=t,e.style.position="fixed",e.style.opacity="0",document.body.appendChild(e),e.select(),document.execCommand("copy"),e.remove()}(t.mac),Pt(this,e("copied"))}}>${e("act_copy_mac")}</button></div>
            <woow-glinet-chart .samples=${this.history} .t=${e} .height=${110}></woow-glinet-chart>
          </div>`:G}
    </div>`}renderFixDialog(){const t=this.fixing;if(!t)return G;const e=this.t;return j`<div class="scrim" @click=${t=>t.target===t.currentTarget&&(this.fixing=null)}>
      <div class="dialog">
        <h2>${e("static_title",{name:vt(t)})}</h2>
        <div class="muted">${e("static_hint")}</div>
        <div class="mono muted">${t.mac}</div>
        <label>${e("ip_address")}
          <input class="mono" .value=${this.fixIp} @input=${t=>this.fixIp=Ut(t)} @keydown=${t=>"Enter"===t.key&&this.confirmFix()} />
        </label>
        <label>${e("device_name")}
          <input .value=${this.fixName} @input=${t=>this.fixName=Ut(t)} @keydown=${t=>"Enter"===t.key&&this.confirmFix()} />
        </label>
        ${this.fixError?j`<div class="error">${this.fixError}</div>`:G}
        <div class="row">
          <span class="grow"></span>
          <button @click=${()=>this.fixing=null}>${e("cancel")}</button>
          <button class="primary" ?disabled=${this.fixBusy||!this.fixIp.trim()||!this.fixName.trim()} @click=${()=>this.confirmFix()}>${e("add")}</button>
        </div>
      </div>
    </div>`}render(){const t=this.t,e=this.visible(),i=this.count("offline");return j`<div class="card">
        <div class="bar">
          <input type="search" .value=${this.query} placeholder=${t("search_ph")} @input=${t=>this.query=Ut(t)} />
          <select @change=${t=>this.sort=Ut(t)} aria-label="sort">
            ${Wt.map(e=>j`<option value=${e} ?selected=${this.sort===e}>${t(`sort_${e}`)}</option>`)}
          </select>
        </div>
        <div class="bar">
          <div class="row filters">
            ${Bt.map(e=>j`<button class=${this.filter===e?"on":""} @click=${()=>this.filter=e}>${t(`f_${e}`)} ${this.count(e)}</button>`)}
          </div>
          <span class="grow"></span>
          ${i?j`<button class="danger" @click=${()=>this.forgetAll()}>${t("forget_all",{n:i})}</button>`:G}
        </div>
        ${0===e.length?j`<div class="empty">${this.router.clients.length?t("clients_empty"):t("clients_none")}</div>`:j`<div class="list">${e.map(t=>this.renderClient(t))}</div>`}
      </div>
      ${this.renderFixDialog()}`}}Rt.styles=[Ct,a`
      .bar {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
        margin-bottom: 12px;
      }
      .bar input[type="search"] {
        flex: 1 1 220px;
      }
      .filters button {
        border-radius: 14px;
        padding: 2px 10px;
        font-size: 0.85em;
      }
      .filters button.on {
        background: var(--primary-color);
        border-color: var(--primary-color);
        color: var(--text-primary-color, #fff);
      }
      .list {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 12px;
      }
      .client {
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 10px;
        padding: 10px 12px;
        display: grid;
        gap: 6px;
        align-content: start;
        background: var(--card-background-color, #fff);
      }
      .client.off .name {
        color: var(--secondary-text-color);
      }
      .name {
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .stats {
        font-variant-numeric: tabular-nums;
        gap: 4px 14px;
      }
      .actions button {
        font-size: 0.85em;
        padding: 3px 9px;
      }
      .detail {
        border-top: 1px dashed var(--divider-color, #e0e0e0);
        padding-top: 8px;
        display: grid;
        gap: 6px;
      }
    `],t([ut({attribute:!1})],Rt.prototype,"router",void 0),t([ut({attribute:!1})],Rt.prototype,"t",void 0),t([ut({attribute:!1})],Rt.prototype,"api",void 0),t([ut({attribute:!1})],Rt.prototype,"now",void 0),t([ft()],Rt.prototype,"query",void 0),t([ft()],Rt.prototype,"filter",void 0),t([ft()],Rt.prototype,"sort",void 0),t([ft()],Rt.prototype,"open",void 0),t([ft()],Rt.prototype,"history",void 0),t([ft()],Rt.prototype,"busy",void 0),t([ft()],Rt.prototype,"fixing",void 0),t([ft()],Rt.prototype,"fixIp",void 0),t([ft()],Rt.prototype,"fixName",void 0),t([ft()],Rt.prototype,"fixError",void 0),t([ft()],Rt.prototype,"fixBusy",void 0),_t("woow-glinet-clients",Rt);const zt={"5m":300,"30m":1800,all:0};class Dt extends lt{constructor(){super(...arguments),this.wan=[],this.now=0,this.range="30m",this.busy=!1}get series(){const t=zt[this.range];if(!t||0===this.wan.length)return this.wan;const e=this.wan[this.wan.length-1][0]-t;return this.wan.filter(t=>t[0]>=e)}async refresh(){this.busy=!0;try{await this.api.refresh(this.router.entry_id)}catch(t){Pt(this,wt(t,this.t),!1)}finally{this.busy=!1}}reboot(){const t=this.t;Mt(this,{title:t("reboot_title",{router:this.router.title}),text:t("reboot_text"),action:t("reboot"),danger:!0,run:async()=>{try{await this.api.reboot(this.router.entry_id),Pt(this,t("rebooting"))}catch(e){Pt(this,wt(e,t),!1)}}})}meter(t,e){const i=e>0?Math.min(100,Math.max(0,t/e*100)):0;return j`<div class="meter"><div class=${i>95?"bad":i>85?"warn":""} style="width:${i.toFixed(0)}%"></div></div>`}fact(t,e){return j`<div><div class="k">${t}</div><div class="v">${e}</div></div>`}renderFacts(){const t=this.router,e=this.t,i=null!=t.uptime?t.uptime+Math.max(0,this.now/1e3-t.fetched_at):null,s=t.memory?t.memory.total-t.memory.free-t.memory.cache:0,o=t.flash?t.flash.total-t.flash.free:0,r=t.clients.filter(t=>t.online).length,a=t.stations.cable??0,n=t.stations.wireless??0;return j`<div class="facts">
      ${this.fact(e("fact_model"),t.model??"—")} ${this.fact(e("fact_firmware"),t.firmware??"—")}
      ${this.fact(e("fact_address"),j`<span class="mono">${t.host}</span>`)}
      ${t.lan_ip&&t.lan_ip!==t.host?this.fact(e("fact_lan"),j`<span class="mono">${t.lan_ip}</span>`):G}
      ${null!=i?this.fact(e("fact_uptime"),function(t){const e=Math.max(0,Math.floor(t)),i=Math.floor(e/86400),s=Math.floor(e%86400/3600),o=Math.floor(e%3600/60);return i?`${i}d ${s}h`:s?`${s}h ${o}m`:`${Math.max(o,0)}m`}(i)):G}
      ${t.load?this.fact(e("fact_load"),t.load.map(t=>t.toFixed(2)).join(" / ")):G}
      ${t.memory?this.fact(e("fact_memory"),j`${e("used_of",{used:Et(s),total:Et(t.memory.total)})}${this.meter(s,t.memory.total)}`):G}
      ${t.flash?this.fact(e("fact_storage"),j`${e("used_of",{used:Et(o),total:Et(t.flash.total)})}${this.meter(o,t.flash.total)}`):G}
      ${this.fact(e("fact_internet"),t.wan.online?j`<span class="chip ok">${e("wan_online")}</span> <span class="muted">${t.wan.links.map(t=>function(t,e){return"wan"===t||"wan6"===t?e("link_wan"):"wwan"===t||"wwan6"===t?e("link_wwan"):t.startsWith("tethering")?e("link_tethering"):t.startsWith("modem")?e("link_modem"):t}(t,e)).join(", ")}</span>`:j`<span class="chip bad">${e("wan_offline")}</span>`)}
      ${"router"===t.mode?this.fact(e("fact_devices"),j`${e("devices_online",{n:r})}<div class="muted">${e("devices_split",{wired:a,wireless:n})}</div>`):G}
    </div>`}renderTraffic(){const t=this.t,e=this.series,i=e[e.length-1],s=Math.max(0,...e.map(t=>t[1])),o=Math.max(0,...e.map(t=>t[2]));return j`<div class="card">
      <div class="row">
        <h2 class="grow" style="margin:0">${t("traffic_title")}</h2>
        <div class="row ranges">
          ${Object.keys(zt).map(e=>j`<button class=${this.range===e?"on":""} @click=${()=>this.range=e}>${t(`range_${e}`)}</button>`)}
        </div>
      </div>
      <div class="big">
        <div><div class="k">${t("download")}</div><div class="num rx">↓ ${St(i?i[1]:this.router.wan.rx)}</div><div class="muted">${t("peak",{x:St(s)})}</div></div>
        <div><div class="k">${t("upload")}</div><div class="num tx">↑ ${St(i?i[2]:this.router.wan.tx)}</div><div class="muted">${t("peak",{x:St(o)})}</div></div>
      </div>
      <woow-glinet-chart .samples=${e} .t=${t}></woow-glinet-chart>
    </div>`}renderBusiest(){const t=this.t,e=this.router.clients.filter(t=>t.online&&t.rx+t.tx>0).sort((t,e)=>e.rx+e.tx-(t.rx+t.tx)).slice(0,6),i=Math.max(1,...e.map(t=>Math.max(t.rx,t.tx))),s=(t,e)=>j`<div class="bar ${t}" style="width:${Math.max(0,e/i*100).toFixed(1)}%"></div>`;return j`<div class="card">
      <h2>${t("busiest_title")}</h2>
      ${0===e.length?j`<div class="muted">${t("busiest_empty")}</div>`:j`<div class="top">
            ${e.map(t=>j`<div class="row" style="flex-wrap:nowrap;align-items:flex-start">
                <div class="who grow">
                  <div class="name"><b>${vt(t)}</b> <span class="muted mono">${t.ip}</span></div>
                  <div class="bars">${s("rx",t.rx)}${s("tx",t.tx)}</div>
                </div>
                <div class="rates"><div class="rx">↓ ${St(t.rx)}</div><div class="tx">↑ ${St(t.tx)}</div></div>
              </div>`)}
          </div>`}
    </div>`}render(){const t=this.router,e=this.t;return j`
      ${t.available?G:j`<div class="banner bad">${e("unreachable")}</div>`}
      ${"router"!==t.mode?j`<div class="banner">${e("mode_note")}</div>`:G}
      <div class="card">
        <div class="row">
          <span class="dot ${t.available?"on":"bad"}"></span>
          <span class="title grow">${t.title}</span>
          <span class="chip ${"router"===t.mode?"ok":"warn"}">${function(t,e){const i=`mode_${t}`;return $t(i)?e(i):e("mode_other",{mode:t})}(t.mode,e)}</span>
        </div>
        <div class="muted" style="margin-top:2px">${e("updated",{x:xt(t.fetched_at,e)})}</div>
        ${this.renderFacts()}
        <div class="row">
          <button ?disabled=${this.busy} @click=${()=>this.refresh()}>${e("refresh")}</button>
          <button class="danger" @click=${()=>this.reboot()}>${e("reboot")}</button>
        </div>
      </div>
      ${"router"===t.mode?j`${this.renderTraffic()}${this.renderBusiest()}`:G}
    `}}Dt.styles=[Ct,a`
      .title {
        font-size: 1.1em;
        font-weight: 500;
      }
      .facts {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 12px 16px;
        margin: 14px 0;
      }
      .k {
        font-size: 0.8em;
        color: var(--secondary-text-color);
      }
      .v {
        margin-top: 2px;
        word-break: break-word;
      }
      .meter {
        height: 6px;
        border-radius: 3px;
        background: var(--secondary-background-color, #eee);
        margin-top: 4px;
        overflow: hidden;
      }
      .meter > div {
        height: 100%;
        background: var(--primary-color);
      }
      .meter > div.warn {
        background: var(--warning-color, #ff9800);
      }
      .meter > div.bad {
        background: var(--error-color, #db4437);
      }
      .ranges button {
        border-radius: 14px;
        padding: 2px 10px;
        font-size: 0.85em;
      }
      .ranges button.on {
        background: var(--primary-color);
        border-color: var(--primary-color);
        color: var(--text-primary-color, #fff);
      }
      .big {
        display: flex;
        flex-wrap: wrap;
        gap: 4px 28px;
        margin: 4px 0 8px;
      }
      .big .num {
        font-size: 1.5em;
        font-weight: 500;
      }
      .top {
        display: grid;
        gap: 10px;
      }
      .top .who {
        min-width: 0;
      }
      .top .name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .bars {
        display: grid;
        gap: 3px;
        margin-top: 4px;
      }
      .bar {
        height: 5px;
        border-radius: 3px;
        min-width: 2px;
      }
      .bar.rx {
        background: var(--success-color, #43a047);
      }
      .bar.tx {
        background: var(--info-color, #039be5);
      }
      .rates {
        text-align: right;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
      }
    `],t([ut({attribute:!1})],Dt.prototype,"router",void 0),t([ut({attribute:!1})],Dt.prototype,"wan",void 0),t([ut({attribute:!1})],Dt.prototype,"t",void 0),t([ut({attribute:!1})],Dt.prototype,"api",void 0),t([ut({attribute:!1})],Dt.prototype,"now",void 0),t([ft()],Dt.prototype,"range",void 0),t([ft()],Dt.prototype,"busy",void 0),_t("woow-glinet-overview",Dt);const Lt=t=>t.target.value,jt=t=>(new TextEncoder).encode(t).length;class qt extends lt{constructor(){super(...arguments),this.edits={},this.revealed={},this.busy=null,this.errors={}}bandLabel(t){return"2G"===t.band?this.t("band_2g"):"5G"===t.band?this.t("band_5g"):t.band}edit(t){return this.edits[t]??{}}setEdit(t,e){this.edits={...this.edits,[t]:{...this.edit(t),...e}}}ssidOf(t){return this.edit(t.name).ssid??t.ssid}problems(t){const e=this.edit(t.name);return{ssid:void 0!==e.ssid&&(jt(e.ssid)<1||jt(e.ssid)>32),key:!!e.key&&(e.key.length<8||e.key.length>63)}}dirty(t){const e=this.edit(t.name);return void 0!==e.ssid&&e.ssid!==t.ssid||!!e.key}async run(t,e){this.busy=t,this.errors={...this.errors,[t]:""};try{await e()}catch(e){this.errors={...this.errors,[t]:wt(e,this.t)}}finally{this.busy=null}}toggle(t){const e=this.t,i=async()=>this.run(t.name,async()=>{await this.api.setWifi(this.router.entry_id,t.name,{enabled:!t.enabled}),Pt(this,e(t.enabled?"wifi_off_toast":"wifi_on_toast",{ssid:t.ssid}))});t.enabled&&!t.guest?Mt(this,{title:e("wifi_confirm_title",{ssid:t.ssid}),text:e("wifi_warn"),action:e("confirm"),danger:!0,run:i}):i()}save(t){const e=this.t,i=this.edit(t.name),s={};void 0!==i.ssid&&i.ssid!==t.ssid&&(s.ssid=i.ssid),i.key&&(s.key=i.key);const o=async()=>this.run(t.name,async()=>{await this.api.setWifi(this.router.entry_id,t.name,s);const{[t.name]:i,...o}=this.edits;this.edits=o;const{[t.name]:r,...a}=this.revealed;this.revealed=a,Pt(this,e("wifi_saved"))});t.guest?o():Mt(this,{title:e("wifi_confirm_title",{ssid:t.ssid}),text:e("wifi_warn"),action:e("save"),danger:!0,run:o})}async reveal(t){if(t.name in this.revealed){const{[t.name]:e,...i}=this.revealed;return void(this.revealed=i)}await this.run(t.name,async()=>{this.revealed={...this.revealed,[t.name]:await this.api.wifiKey(this.router.entry_id,t.name)}})}renderIface(t,e){const i=this.t,s=this.problems(e),o=this.busy===e.name,r=this.edit(e.name);return j`<div class="card ${o?"busy":""}">
      <div class="row">
        <span class="dot ${e.up?"on":""}" title=${e.up?i("on_air"):i("radio_off")}></span>
        <span class="ssid grow">${e.ssid}</span>
        <span class="chip">${this.bandLabel(t)}</span>
        ${e.guest?j`<span class="chip info">${i("guest")}</span>`:G}
        ${e.hidden?j`<span class="chip">${i("hidden")}</span>`:G}
        <button class="switch ${e.enabled?"on":""}" role="switch" aria-checked=${e.enabled} aria-label=${i("enabled")}
          ?disabled=${o} @click=${()=>this.toggle(e)}></button>
      </div>
      <div class="muted">
        ${e.up?i("on_air"):i("radio_off")} · ${i("wifi_enc")} ${e.encryption}
        · ${i("wifi_channel")} ${t.channel&&0!==t.channel?t.channel:i("channel_auto")}
        · <span class="mono">${e.bssid}</span>
      </div>
      <div class="form">
        <label>${i("ssid")}
          <input class=${s.ssid?"bad":""} .value=${this.ssidOf(e)} @input=${t=>this.setEdit(e.name,{ssid:Lt(t)})} />
        </label>
        <label>${i("password")}
          <input class=${s.key?"bad":""} type="password" autocomplete="new-password" placeholder=${i("password_ph")} .value=${r.key??""}
            @input=${t=>this.setEdit(e.name,{key:Lt(t)})} />
          <span class="row">
            <button class="link" ?disabled=${o} @click=${()=>this.reveal(e)}>${e.name in this.revealed?i("hide"):i("show_password")}</button>
            ${e.name in this.revealed?j`<span class="mono">${this.revealed[e.name]}</span>`:G}
          </span>
        </label>
      </div>
      ${this.dirty(e)&&!e.guest?j`<div class="banner">${i("wifi_warn")}</div>`:G}
      ${this.errors[e.name]?j`<div class="error">${this.errors[e.name]}</div>`:G}
      <div class="row">
        <span class="grow"></span>
        ${this.dirty(e)?j`<button @click=${()=>{const{[e.name]:t,...i}=this.edits;this.edits=i}}>${i("cancel")}</button>`:G}
        <button class="primary" ?disabled=${o||!this.dirty(e)||s.ssid||s.key} @click=${()=>this.save(e)}>${i(o?"saving":"save")}</button>
      </div>
    </div>`}render(){const t=this.router.wifi;return t.some(t=>t.ifaces.length)?j`${t.map(t=>t.ifaces.map(e=>this.renderIface(t,e)))}`:j`<div class="card"><div class="empty">${this.t("wifi_empty")}</div></div>`}}qt.styles=[Ct,a`
      .ssid {
        font-size: 1.05em;
        font-weight: 500;
      }
      .switch {
        position: relative;
        width: 44px;
        height: 24px;
        border-radius: 12px;
        border: none;
        padding: 0;
        background: var(--disabled-text-color, #bdbdbd);
        flex: none;
      }
      .switch::after {
        content: "";
        position: absolute;
        top: 2px;
        left: 2px;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background: #fff;
        transition: transform 0.15s;
      }
      .switch.on {
        background: var(--primary-color);
      }
      .switch.on::after {
        transform: translateX(20px);
      }
      .form {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 10px 16px;
        margin: 12px 0 8px;
      }
      .form label {
        display: grid;
        gap: 4px;
        font-size: 0.85em;
        color: var(--secondary-text-color);
      }
      .form input {
        font-size: 1.05em;
      }
      .card.busy {
        opacity: 0.65;
        pointer-events: none;
      }
      .form input.bad {
        outline: 2px solid var(--error-color, #db4437);
        outline-offset: -1px;
      }
    `],t([ut({attribute:!1})],qt.prototype,"router",void 0),t([ut({attribute:!1})],qt.prototype,"t",void 0),t([ut({attribute:!1})],qt.prototype,"api",void 0),t([ft()],qt.prototype,"edits",void 0),t([ft()],qt.prototype,"revealed",void 0),t([ft()],qt.prototype,"busy",void 0),t([ft()],qt.prototype,"errors",void 0),_t("woow-glinet-wifi",qt);class Vt extends lt{constructor(){super(...arguments),this.narrow=!1,this.tab="overview",this.routers={},this.wan={},this.selected="",this.activity=[],this.loaded=!1,this.error="",this.now=Date.now(),this.toast=null,this.confirmReq=null,this.confirmBusy=!1,this.t=yt("en"),this.api=new mt(()=>this._hass),this.connecting=!1}set hass(t){const e=!this._hass;this._hass=t,e&&(this.t=yt(t.locale?.language??t.language??"en"),this.isConnected&&this.connect(),this.requestUpdate())}get hass(){return this._hass}connectedCallback(){super.connectedCallback(),this._hass&&!this.unsubscribe&&this.connect(),this.ticker=window.setInterval(()=>this.now=Date.now(),5e3)}disconnectedCallback(){super.disconnectedCallback(),window.clearInterval(this.ticker),window.clearTimeout(this.toastTimer),this.unsubscribe?.(),this.unsubscribe=void 0}async connect(){if(!this.connecting&&!this.unsubscribe){this.connecting=!0;try{this.unsubscribe=await this.api.subscribe(t=>this.onEvent(t));const t=await this.api.snapshot();this.routers=Object.fromEntries(t.routers.map(t=>[t.entry_id,t])),this.wan=Object.fromEntries(t.routers.map(t=>[t.entry_id,t.history?.wan??[]])),this.activity=t.activity,this.loaded=!0,this.error=""}catch(t){this.error=function(t){return String(t&&"object"==typeof t&&"message"in t?t.message:t)}(t)}finally{this.connecting=!1}}}onEvent(t){switch(t.kind){case"router":{const e=t.router.entry_id;this.routers={...this.routers,[e]:t.router},e in this.wan||(this.wan={...this.wan,[e]:[]});break}case"router_removed":{const{[t.entry_id]:e,...i}=this.routers;this.routers=i;break}case"live":{const e=this.routers[t.entry_id];if(!e)break;this.routers={...this.routers,[t.entry_id]:{...e,available:!0,clients:t.clients,wan:{...e.wan,rx:t.wan.rx,tx:t.wan.tx}}};const i=[...this.wan[t.entry_id]??[],[t.t,t.wan.rx,t.wan.tx]];this.wan={...this.wan,[t.entry_id]:i.slice(-1500)};break}case"activity":this.activity=[...t.entries.reverse(),...this.activity].slice(0,300)}}get routerList(){return Object.values(this.routers).sort((t,e)=>t.title.localeCompare(e.title))}get current(){return this.routers[this.selected]??this.routerList[0]}tabsFor(t){return t&&"router"!==t.mode?["overview","wifi","activity"]:["overview","clients","wifi","access","activity"]}toggleMenu(){this.dispatchEvent(new Event("hass-toggle-menu",{bubbles:!0,composed:!0}))}showToast(t){this.toast=t.detail,window.clearTimeout(this.toastTimer),this.toastTimer=window.setTimeout(()=>this.toast=null,t.detail.ok?3500:7e3)}async runConfirm(){const t=this.confirmReq;if(t&&!this.confirmBusy){this.confirmBusy=!0;try{await t.run()}finally{this.confirmBusy=!1,this.confirmReq=null}}}renderConfirm(){const t=this.confirmReq;if(!t)return G;const e=this.t;return j`<div class="scrim" @click=${t=>t.target===t.currentTarget&&!this.confirmBusy&&(this.confirmReq=null)}>
      <div class="dialog" role="dialog">
        <h2>${t.title}</h2>
        ${t.text?j`<div class="muted">${t.text}</div>`:G}
        <div class="row">
          <span class="grow"></span>
          <button ?disabled=${this.confirmBusy} @click=${()=>this.confirmReq=null}>${e("cancel")}</button>
          <button class="primary ${t.danger?"danger":""}" ?disabled=${this.confirmBusy} @click=${()=>this.runConfirm()}>${t.action}</button>
        </div>
      </div>
    </div>`}renderTab(t,e){const i=t,s=this.t,o=this.api;switch(e){case"clients":return j`<woow-glinet-clients .router=${i} .t=${s} .api=${o} .now=${this.now}></woow-glinet-clients>`;case"wifi":return j`<woow-glinet-wifi .router=${i} .t=${s} .api=${o}></woow-glinet-wifi>`;case"access":return j`<woow-glinet-access .router=${i} .t=${s} .api=${o}></woow-glinet-access>`;case"activity":{const e=this.activity.filter(e=>!e.entry_id||this.routerList.length<2||e.entry_id===t.entry_id);return j`<woow-glinet-activity .entries=${e} .t=${this.t} .now=${this.now} ?multi=${this.routerList.length>1}></woow-glinet-activity>`}default:return j`<woow-glinet-overview .router=${i} .wan=${this.wan[t.entry_id]??[]} .t=${s} .api=${o} .now=${this.now}></woow-glinet-overview>`}}render(){const t=this.t,e=this.current,i=this.tabsFor(e),s=i.includes(this.tab)?this.tab:"overview",o=e?e.clients.filter(t=>t.online).length:0,r={clients:o,access:e?e.blocklist.black.length:0};return j`
      <div class="toolbar">
        ${this.narrow?j`<button @click=${this.toggleMenu} aria-label="menu">
              <svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d=${"M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z"}></path></svg>
            </button>`:G}
        <div>${t("title")}</div>
      </div>
      <div class="tabs">
        ${i.map(e=>j`<button class="tab ${s===e?"active":""}" @click=${()=>this.tab=e}>
            ${t(`tab_${e}`)}${r[e]?j`<span class="count">${r[e]}</span>`:G}
          </button>`)}
      </div>
      <div class="content" @notify=${t=>this.showToast(t)}
        @confirm=${t=>this.confirmReq=t.detail}>
        ${this.error?j`<div class="card"><div class="error">${t("error",{msg:this.error})}</div></div>`:this.loaded?e?j`${this.routerList.length>1?j`<div class="row picker">
                        <span class="muted">${t("router_pick")}</span>
                        <select @change=${t=>this.selected=t.target.value}>
                          ${this.routerList.map(t=>j`<option value=${t.entry_id} ?selected=${t.entry_id===e.entry_id}>${t.title}</option>`)}
                        </select>
                      </div>`:G}
                  ${this.renderTab(e,s)}`:j`<div class="empty">${t("no_routers")}</div>`:j`<div class="empty">${t("loading")}</div>`}
      </div>
      ${this.renderConfirm()}
      ${this.toast?j`<div class="toast ${this.toast.ok?"":"bad"}">${this.toast.text}</div>`:G}
    `}}Vt.styles=[Ct,a`
      :host {
        min-height: 100vh;
        background: var(--primary-background-color);
      }
      .toolbar {
        display: flex;
        align-items: center;
        gap: 8px;
        height: 56px;
        padding: 0 16px;
        background: var(--app-header-background-color, var(--primary-color));
        color: var(--app-header-text-color, var(--text-primary-color, #fff));
        font-size: 20px;
      }
      .toolbar button {
        border: none;
        background: none;
        color: inherit;
        padding: 8px;
        line-height: 0;
      }
      .tabs {
        display: flex;
        gap: 4px;
        padding: 0 12px;
        background: var(--app-header-background-color, var(--primary-color));
        overflow-x: auto;
      }
      .tab {
        border: none;
        border-bottom: 3px solid transparent;
        border-radius: 0;
        background: none;
        color: var(--app-header-text-color, var(--text-primary-color, #fff));
        opacity: 0.75;
        padding: 10px 14px;
        white-space: nowrap;
      }
      .tab.active {
        opacity: 1;
        border-bottom-color: var(--app-header-text-color, var(--text-primary-color, #fff));
      }
      .content {
        max-width: 1200px;
        margin: 0 auto;
        padding: 16px;
      }
      .count {
        margin-left: 6px;
        font-size: 0.8em;
        opacity: 0.85;
      }
      .picker {
        margin-bottom: 12px;
      }
      .toast {
        position: fixed;
        left: 50%;
        bottom: 24px;
        transform: translateX(-50%);
        z-index: 20;
        max-width: min(520px, calc(100vw - 32px));
        padding: 10px 16px;
        border-radius: 10px;
        background: var(--primary-text-color);
        color: var(--card-background-color, #fff);
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.35);
        font-size: 0.95em;
      }
      .toast.bad {
        background: var(--error-color, #db4437);
        color: #fff;
      }
    `],t([ut({attribute:!1})],Vt.prototype,"narrow",void 0),t([ut({attribute:!1})],Vt.prototype,"route",void 0),t([ut({attribute:!1})],Vt.prototype,"panel",void 0),t([ft()],Vt.prototype,"tab",void 0),t([ft()],Vt.prototype,"routers",void 0),t([ft()],Vt.prototype,"wan",void 0),t([ft()],Vt.prototype,"selected",void 0),t([ft()],Vt.prototype,"activity",void 0),t([ft()],Vt.prototype,"loaded",void 0),t([ft()],Vt.prototype,"error",void 0),t([ft()],Vt.prototype,"now",void 0),t([ft()],Vt.prototype,"toast",void 0),t([ft()],Vt.prototype,"confirmReq",void 0),t([ft()],Vt.prototype,"confirmBusy",void 0),_t("woow-glinet-panel",Vt);export{Vt as WoowGlinetPanel};

{% if cv.name %}
= {{ cv.name }}
{% endif %}

#connections(
{% for connection in cv._connections[:2] %}
  [{% if loop.index == 1 %}Email: {% else %}Location: {% endif %}{{ connection }}],
{% endfor %}
)
#linebreak()
#connections(
  [Website: {{ cv._connections[2] }}],
{% for social in cv.social_networks %}
  [#link("{{ social.url }}", icon: false, if-underline: false, if-color: false)[#connection-with-icon("{{ social.network | lower }}")[{{ social.network }}]]],
{% endfor %}
)

// The discussion of a case: open after one's own verdict; accounts write and back comments.
import 'package:flutter/material.dart';

import '../api.dart';
import '../main.dart';
import '../theme.dart';
import '../widgets.dart';

class TalkScreen extends StatefulWidget {
  const TalkScreen({super.key, required this.caseId, required this.title});

  final int caseId;
  final String title;

  @override
  State<TalkScreen> createState() => _TalkScreenState();
}

class _TalkScreenState extends State<TalkScreen> {
  String _sort = 'top';
  Json? _data;
  ApiException? _locked;
  Object? _error;
  bool _sending = false;
  final _text = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final d = await SessionScope.read(context).api.get('/cases/${widget.caseId}/comments', query: {'sort': _sort});
      if (mounted) {
        setState(() {
          _data = d;
          _locked = null;
        });
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => e.status == 403 ? _locked = e : _error = e);
    }
  }

  Future<void> _send() async {
    final text = _text.text.trim();
    if (text.length < 3) return;
    setState(() => _sending = true);
    try {
      await SessionScope.read(context).api.post('/cases/${widget.caseId}/comments', {'text': text});
      _text.clear();
      _sort = 'new';
      await _load();
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _like(Json c) async {
    final api = SessionScope.read(context).api;
    try {
      final out = await api.post('/comments/${c['id']}/${c['liked'] == true ? 'unlike' : 'like'}');
      setState(() {
        c['likes'] = out['likes'];
        if (out['done'] == true) c['liked'] = !(c['liked'] == true);
      });
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    Widget body;
    if (_locked != null) {
      final n = (_locked!.body?['count'] as num?)?.toInt() ?? 0;
      body = ListView(padding: const EdgeInsets.all(28), children: [
        const SizedBox(height: 30),
        const Icon(Icons.lock_outline, size: 48, color: V.cyan),
        const SizedBox(height: 14),
        Text('Обсуждение откроется после вашего вердикта', textAlign: TextAlign.center, style: V.display(19)),
        const SizedBox(height: 10),
        Text(n > 0 ? 'Здесь уже спорят: $n ${plural(n, 'комментарий', 'комментария', 'комментариев')}.' : 'Здесь спорят о решениях — и выдают, к чему склоняется большинство.',
            textAlign: TextAlign.center, style: V.body(14, color: V.muted)),
      ]);
    } else if (_error != null) {
      body = ErrorView(_error!, onRetry: _load);
    } else if (_data == null) {
      body = const Loading();
    } else {
      final items = (_data!['comments'] as List).cast<Json>();
      body = RefreshIndicator(
        color: V.cyan,
        onRefresh: _load,
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 16), children: [
          SegmentedButton<String>(
            segments: const [ButtonSegment(value: 'top', label: Text('Лучшие')), ButtonSegment(value: 'new', label: Text('Новые'))],
            selected: {_sort},
            onSelectionChanged: (v) {
              _sort = v.first;
              _load();
            },
          ),
          const SizedBox(height: 12),
          if (items.isEmpty)
            Padding(
              padding: const EdgeInsets.all(24),
              child: Text('Пока тихо. Объясните свой вердикт первым — с ним будут спорить.',
                  textAlign: TextAlign.center, style: V.body(14, color: V.muted)),
            ),
          for (final c in items) _comment(c, s.signedIn),
        ]),
      );
    }
    return Scaffold(
      appBar: AppBar(title: Text('Обсуждение: ${widget.title}', overflow: TextOverflow.ellipsis)),
      body: Column(children: [
        Expanded(child: body),
        if (_data != null)
          SafeArea(
            top: false,
            child: Container(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
              decoration: const BoxDecoration(color: Color(0xFF060818), border: Border(top: BorderSide(color: V.line))),
              child: s.signedIn
                  ? Row(children: [
                      Expanded(
                        child: TextField(
                          controller: _text,
                          minLines: 1,
                          maxLines: 4,
                          maxLength: 1000,
                          decoration: const InputDecoration(hintText: 'Почему вы решили так?', counterText: '', isDense: true),
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton.filled(
                        onPressed: _sending ? null : _send,
                        icon: _sending
                            ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                            : const Icon(Icons.send),
                        style: IconButton.styleFrom(backgroundColor: V.cyan, foregroundColor: V.bg),
                      ),
                    ])
                  : Text('Войдите во вкладке «Войти», чтобы высказаться и поддерживать других.',
                      textAlign: TextAlign.center, style: V.body(13, color: V.muted)),
            ),
          ),
      ]),
    );
  }

  Widget _comment(Json c, bool signedIn) {
    final author = c['author'] as Json;
    final mine = _data?['my_verdict'];
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Panel(
        accent: c['mine'] == true ? V.cyan : null,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Avatar(author['display_name'] as String, size: 32),
            const SizedBox(width: 10),
            Expanded(child: Text(author['display_name'] as String, style: V.body(14, weight: FontWeight.w800))),
            OptionLetter((c['option'] as String?) ?? '?', size: 26),
            if (mine != null && c['option'] == mine && c['mine'] != true) ...[
              const SizedBox(width: 6),
              const Pill('как вы', color: V.cyan),
            ],
          ]),
          const SizedBox(height: 10),
          Text(c['text'] as String, style: V.body(15)),
          const SizedBox(height: 8),
          Row(children: [
            Text(ruDate(c['created_at'] as String), style: V.body(12, color: V.dim)),
            const Spacer(),
            TextButton.icon(
              onPressed: signedIn && c['mine'] != true ? () => _like(c) : null,
              icon: Icon(c['liked'] == true ? Icons.favorite : Icons.favorite_border, size: 18,
                  color: c['liked'] == true ? V.magenta : V.muted),
              label: Text('${c['likes']}', style: V.body(13, weight: FontWeight.w700, color: V.muted)),
            ),
          ]),
        ]),
      ),
    );
  }
}

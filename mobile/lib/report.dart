// «Пожаловаться»: a reason from the catalog and a note go to the team (POST /reports), as on the website.
import 'package:flutter/material.dart';

import 'api.dart';
import 'links.dart';
import 'main.dart';
import 'theme.dart';
import 'widgets.dart';

/// [target]: user (with [login]), community (with [slug]), case or comment (with [id]); [what] names it for the player.
Future<void> report(
  BuildContext context, {
  required String target,
  required String what,
  String? login,
  String? slug,
  int? id,
}) async {
  final s = SessionScope.read(context);
  if (!s.signedIn) {
    snack(context, 'Войдите, чтобы отправить жалобу.');
    return;
  }
  final body = <String, dynamic>{'target': target, 'login': ?login, 'slug': ?slug, 'id': ?id};
  final msg = await showModalBottomSheet<String>(
    context: context,
    isScrollControlled: true,
    backgroundColor: V.panel2,
    builder: (_) => _ReportSheet(what: what, body: body),
  );
  if (msg != null && context.mounted) snack(context, msg);
}

class _ReportSheet extends StatefulWidget {
  const _ReportSheet({required this.what, required this.body});

  final String what;
  final Json body;

  @override
  State<_ReportSheet> createState() => _ReportSheetState();
}

class _ReportSheetState extends State<_ReportSheet> {
  String? _reason;
  bool _busy = false;
  String? _error;
  final _text = TextEditingController();

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final out = await SessionScope.read(context).api
          .post('/reports', {...widget.body, 'reason': _reason, 'text': _text.text.trim()});
      if (mounted) {
        Navigator.pop(
          context,
          out['new'] == false ? 'Вы уже пожаловались — команда посмотрит.' : 'Спасибо! Команда посмотрит жалобу.',
        );
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final reasons = (SessionScope.of(context).catalog['report_reasons'] as Json?) ?? const {};
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(16, 18, 16, 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Пожаловаться', style: V.display(18)),
              const SizedBox(height: 4),
              Text(widget.what, style: V.body(13.5, color: V.muted)),
              const SizedBox(height: 10),
              RadioGroup<String>(
                groupValue: _reason,
                onChanged: (v) => setState(() => _reason = v),
                child: Column(
                  children: [
                    for (final r in reasons.entries)
                      RadioListTile<String>(
                        value: r.key,
                        title: Text('${r.value}'),
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                      ),
                  ],
                ),
              ),
              TextField(
                controller: _text,
                maxLength: 500,
                minLines: 2,
                maxLines: 4,
                decoration: const InputDecoration(hintText: 'Что случилось — необязательно'),
              ),
              if (_error != null) Text(_error!, style: V.body(13, color: V.red)),
              const SizedBox(height: 8),
              GradientButton(
                'Отправить команде',
                icon: Icons.flag,
                busy: _busy,
                onPressed: _reason == null ? null : _send,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

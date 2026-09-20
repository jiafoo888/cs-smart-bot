# SteelShop Payment & Invoice Policy

## Supported Payment Methods
WeChat Pay, Alipay, bank card, and account balance.
After a successful payment the order moves to `paid` or into fulfillment.

## Failed Payments
If payment status is `failed` or `pending`, do not place a duplicate order.
Switch methods or wait for the bank callback (usually within 30 minutes).

## Duplicate Charges
If the system shows success but the customer was charged twice, provide the payment id
(`PAY-xxxx`) or bank reference. Extra charges are refunded to the original method after verification.

## E-Invoices
Request an e-invoice from the order page; it is usually issued within 24 hours.
After a refund, a previously issued invoice must be voided and re-issued if needed.

## Wire Transfers
Enterprise customers may pay by bank wire. Ops marks payment succeeded after funds clear
(typically 1 business day).
